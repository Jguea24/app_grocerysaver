"""Servicios transaccionales del dominio de ordenes."""

import uuid
from decimal import Decimal

from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone

from grocerysaver.models import Address, Cart, CartItem, ProductPrice

from .models import CheckoutItem, CheckoutSession, CheckoutStatus, Order, OrderItem, OrderStatus, Payment, PaymentStatus, Shipment, ShipmentStatus


UNSET = object()


class OrderCreationError(Exception):
    """Error de negocio para la creacion de una orden, checkout, pago o envio."""

    def __init__(self, detail, *, status_code=400):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


SHIPMENT_ALLOWED_TRANSITIONS = {
    ShipmentStatus.PENDING: {ShipmentStatus.PREPARING, ShipmentStatus.CANCELLED},
    ShipmentStatus.PREPARING: {ShipmentStatus.SHIPPED, ShipmentStatus.CANCELLED},
    ShipmentStatus.SHIPPED: {ShipmentStatus.DELIVERED, ShipmentStatus.CANCELLED},
    ShipmentStatus.DELIVERED: set(),
    ShipmentStatus.CANCELLED: set(),
}


def load_checkout_cart(user):
    """Carga el carrito del usuario con las relaciones necesarias para checkout u orden."""
    cart = Cart.objects.filter(user=user).first()
    if cart is None:
        return None
    return (
        Cart.objects.select_related('user')
        .prefetch_related(
            Prefetch(
                'items',
                queryset=CartItem.objects.select_related('product__category', 'store').prefetch_related(
                    Prefetch('product__prices', queryset=ProductPrice.objects.select_related('store').order_by('price')),
                ),
            )
        )
        .get(id=cart.id)
    )


def clear_user_cart(user):
    """Vacia el carrito persistido del usuario cuando el flujo ya fue convertido."""
    cart = Cart.objects.filter(user=user).first()
    if cart is None:
        return
    cart.items.all().delete()
    cart.updated_at = timezone.now()
    cart.save(update_fields=['updated_at'])


def resolve_cart_item_price_row(item):
    """Resuelve el precio vigente de la linea del carrito."""
    prices = list(item.product.prices.all())
    if not prices:
        return None
    if item.store_id is None:
        return prices[0]
    for price_row in prices:
        if price_row.store_id == item.store_id:
            return price_row
    return None


def build_cart_snapshot(cart):
    """Construye snapshot de lineas y totales a partir del carrito actual."""
    if cart is None or not cart.items.exists():
        raise OrderCreationError('El carrito esta vacio.')

    lines = []
    subtotal = Decimal('0.00')
    total_items = 0

    for item in cart.items.all():
        price_row = resolve_cart_item_price_row(item)
        if price_row is None:
            raise OrderCreationError(f'El producto {item.product.name} no tiene precio disponible para continuar con checkout.')

        line_total = price_row.price * item.quantity
        subtotal += line_total
        total_items += item.quantity
        lines.append(
            {
                'product': item.product,
                'store': price_row.store,
                'product_name': item.product.name,
                'product_brand': item.product.brand,
                'category_name': item.product.category.name,
                'store_name': price_row.store.name,
                'quantity': item.quantity,
                'unit_price': price_row.price,
                'line_total': line_total,
            }
        )

    delivery_fee = Decimal('0.00')
    total = subtotal + delivery_fee
    return {'lines': lines, 'total_items': total_items, 'subtotal': subtotal, 'delivery_fee': delivery_fee, 'total': total}


def snapshot_address_fields(address):
    """Convierte una direccion del usuario en un snapshot inmutable."""
    return {
        'address': address,
        'address_label': address.label,
        'contact_name': address.contact_name,
        'phone': address.phone,
        'line1': address.line1,
        'line2': address.line2,
        'city': address.city,
    }


def snapshot_order_address_fields(order):
    """Convierte la direccion ya congelada de la orden en snapshot para envio."""
    return {
        'contact_name': order.contact_name,
        'phone': order.phone,
        'line1': order.line1,
        'line2': order.line2,
        'city': order.city,
    }


def build_checkout_snapshot(checkout):
    """Construye snapshot de lineas y totales a partir de un checkout persistido."""
    if not checkout.items.exists():
        raise OrderCreationError('El checkout no tiene items para procesar el pago.')

    lines = []
    for item in checkout.items.all():
        lines.append(
            {
                'product': item.product,
                'store': item.store,
                'product_name': item.product_name,
                'product_brand': item.product_brand,
                'category_name': item.category_name,
                'store_name': item.store_name,
                'quantity': item.quantity,
                'unit_price': item.unit_price,
                'line_total': item.line_total,
            }
        )

    return {
        'lines': lines,
        'total_items': checkout.total_items,
        'subtotal': checkout.subtotal,
        'delivery_fee': checkout.delivery_fee,
        'total': checkout.total,
    }


@transaction.atomic
def create_checkout_from_cart(*, user, notes=''):
    """Crea una sesion de checkout abierta a partir del carrito actual sin vaciarlo."""
    cart = load_checkout_cart(user)
    snapshot = build_cart_snapshot(cart)

    checkout = CheckoutSession.objects.create(
        user=user,
        status=CheckoutStatus.OPEN,
        notes=notes,
        total_items=snapshot['total_items'],
        subtotal=snapshot['subtotal'],
        delivery_fee=snapshot['delivery_fee'],
        total=snapshot['total'],
    )

    CheckoutItem.objects.bulk_create([
        CheckoutItem(
            checkout=checkout,
            product=line['product'],
            store=line['store'],
            product_name=line['product_name'],
            product_brand=line['product_brand'],
            category_name=line['category_name'],
            store_name=line['store_name'],
            quantity=line['quantity'],
            unit_price=line['unit_price'],
            line_total=line['line_total'],
        )
        for line in snapshot['lines']
    ])

    return CheckoutSession.objects.select_related('address').prefetch_related('items').get(id=checkout.id)


@transaction.atomic
def update_checkout_session(*, user, checkout, address_id=None, notes=None):
    """Adjunta direccion y actualiza notas de una sesion de checkout existente."""
    updates = []

    if notes is not None:
        checkout.notes = notes
        updates.append('notes')

    if address_id is not None:
        address = Address.objects.filter(id=address_id, user=user).first()
        if address is None:
            raise OrderCreationError('Direccion no encontrada.', status_code=404)
        address_snapshot = snapshot_address_fields(address)
        checkout.address = address_snapshot['address']
        checkout.address_label = address_snapshot['address_label']
        checkout.contact_name = address_snapshot['contact_name']
        checkout.phone = address_snapshot['phone']
        checkout.line1 = address_snapshot['line1']
        checkout.line2 = address_snapshot['line2']
        checkout.city = address_snapshot['city']
        checkout.status = CheckoutStatus.READY_FOR_PAYMENT
        updates.extend(['address', 'address_label', 'contact_name', 'phone', 'line1', 'line2', 'city', 'status'])

    if updates:
        updates.append('updated_at')
        checkout.save(update_fields=updates)

    return CheckoutSession.objects.select_related('address').prefetch_related('items').get(id=checkout.id)


@transaction.atomic
def create_order_from_checkout(*, checkout):
    """Convierte un checkout listo en una orden colocada."""
    if checkout.status != CheckoutStatus.READY_FOR_PAYMENT:
        raise OrderCreationError('El checkout no esta listo para pago.')

    existing_order = Order.objects.filter(checkout=checkout).first()
    if existing_order is not None:
        return existing_order

    snapshot = build_checkout_snapshot(checkout)
    order = Order.objects.create(
        user=checkout.user,
        checkout=checkout,
        address=checkout.address,
        status=OrderStatus.PLACED,
        address_label=checkout.address_label,
        contact_name=checkout.contact_name,
        phone=checkout.phone,
        line1=checkout.line1,
        line2=checkout.line2,
        city=checkout.city,
        notes=checkout.notes,
        total_items=snapshot['total_items'],
        subtotal=snapshot['subtotal'],
        delivery_fee=snapshot['delivery_fee'],
        total=snapshot['total'],
    )

    OrderItem.objects.bulk_create([
        OrderItem(
            order=order,
            product=line['product'],
            store=line['store'],
            product_name=line['product_name'],
            product_brand=line['product_brand'],
            category_name=line['category_name'],
            store_name=line['store_name'],
            quantity=line['quantity'],
            unit_price=line['unit_price'],
            line_total=line['line_total'],
        )
        for line in snapshot['lines']
    ])

    checkout.status = CheckoutStatus.CONVERTED
    checkout.save(update_fields=['status', 'updated_at'])
    clear_user_cart(checkout.user)
    return Order.objects.select_related('address', 'checkout').prefetch_related('items').get(id=order.id)


def ensure_shipment_for_order(order):
    """Crea o reutiliza el envio asociado a una orden ya pagada."""
    if order.status != OrderStatus.PLACED:
        raise OrderCreationError('Solo se puede crear envio para ordenes colocadas.')

    shipment = getattr(order, 'shipment', None)
    if shipment is not None:
        return shipment

    address_snapshot = snapshot_order_address_fields(order)
    return Shipment.objects.create(
        user=order.user,
        order=order,
        status=ShipmentStatus.PENDING,
        contact_name=address_snapshot['contact_name'],
        phone=address_snapshot['phone'],
        line1=address_snapshot['line1'],
        line2=address_snapshot['line2'],
        city=address_snapshot['city'],
        notes=order.notes,
    )


@transaction.atomic
def update_shipment_status(*, user, shipment, status_value=UNSET, carrier=UNSET, tracking_number=UNSET, notes=UNSET, estimated_delivery_at=UNSET):
    """Actualiza el estado y metadatos del envio respetando transiciones basicas."""
    if shipment.user_id != user.id:
        raise OrderCreationError('Envio no encontrado.', status_code=404)

    updates = []
    now = timezone.now()

    if status_value is not UNSET and status_value != shipment.status:
        allowed = SHIPMENT_ALLOWED_TRANSITIONS.get(shipment.status, set())
        if status_value not in allowed:
            raise OrderCreationError(f'No se puede cambiar el envio de {shipment.status} a {status_value}.')
        shipment.status = status_value
        updates.append('status')

        if status_value == ShipmentStatus.SHIPPED and shipment.shipped_at is None:
            shipment.shipped_at = now
            updates.append('shipped_at')
        if status_value == ShipmentStatus.DELIVERED and shipment.delivered_at is None:
            if shipment.shipped_at is None:
                shipment.shipped_at = now
                updates.append('shipped_at')
            shipment.delivered_at = now
            updates.append('delivered_at')

    if carrier is not UNSET:
        shipment.carrier = carrier
        updates.append('carrier')
    if tracking_number is not UNSET:
        shipment.tracking_number = tracking_number
        updates.append('tracking_number')
    if notes is not UNSET:
        shipment.notes = notes
        updates.append('notes')
    if estimated_delivery_at is not UNSET:
        shipment.estimated_delivery_at = estimated_delivery_at
        updates.append('estimated_delivery_at')

    if updates:
        updates.append('updated_at')
        shipment.save(update_fields=list(dict.fromkeys(updates)))

    return Shipment.objects.select_related('order').get(id=shipment.id)


@transaction.atomic
def process_checkout_payment(*, user, checkout_id, method, provider='sandbox', simulate_failure=False):
    """Procesa un pago simulado sobre un checkout y crea la orden cuando es exitoso."""
    checkout = CheckoutSession.objects.select_related('address').prefetch_related('items').filter(id=checkout_id, user=user).first()
    if checkout is None:
        raise OrderCreationError('Checkout no encontrado.', status_code=404)
    if checkout.status != CheckoutStatus.READY_FOR_PAYMENT:
        raise OrderCreationError('El checkout debe tener direccion y estar listo para pago antes de cobrar.')
    if Payment.objects.filter(checkout=checkout, status=PaymentStatus.SUCCEEDED).exists():
        raise OrderCreationError('El checkout ya fue pagado.')

    payment = Payment.objects.create(
        user=user,
        checkout=checkout,
        method=method,
        provider=provider or 'sandbox',
        status=PaymentStatus.PENDING,
        amount=checkout.total,
        currency='USD',
    )

    if simulate_failure:
        payment.status = PaymentStatus.FAILED
        payment.failure_reason = 'Pago rechazado por simulacion.'
        payment.save(update_fields=['status', 'failure_reason', 'updated_at'])
        return Payment.objects.select_related('order', 'checkout').get(id=payment.id)

    order = create_order_from_checkout(checkout=checkout)
    ensure_shipment_for_order(order)
    payment.order = order
    payment.status = PaymentStatus.SUCCEEDED
    payment.provider_reference = f'sandbox-{uuid.uuid4().hex[:12]}'
    payment.paid_at = timezone.now()
    payment.save(update_fields=['order', 'status', 'provider_reference', 'paid_at', 'updated_at'])

    return Payment.objects.select_related('order__shipment', 'checkout').get(id=payment.id)


@transaction.atomic
def create_order_from_cart(*, user, address_id, notes=''):
    """Convierte el carrito actual del usuario en una orden pendiente de pago."""
    address = Address.objects.filter(id=address_id, user=user).first()
    if address is None:
        raise OrderCreationError('Direccion no encontrada.', status_code=404)

    cart = load_checkout_cart(user)
    snapshot = build_cart_snapshot(cart)
    address_snapshot = snapshot_address_fields(address)

    order = Order.objects.create(
        user=user,
        checkout=None,
        address=address_snapshot['address'],
        status=OrderStatus.PENDING_PAYMENT,
        address_label=address_snapshot['address_label'],
        contact_name=address_snapshot['contact_name'],
        phone=address_snapshot['phone'],
        line1=address_snapshot['line1'],
        line2=address_snapshot['line2'],
        city=address_snapshot['city'],
        notes=notes,
        total_items=snapshot['total_items'],
        subtotal=snapshot['subtotal'],
        delivery_fee=snapshot['delivery_fee'],
        total=snapshot['total'],
    )

    OrderItem.objects.bulk_create([
        OrderItem(
            order=order,
            product=line['product'],
            store=line['store'],
            product_name=line['product_name'],
            product_brand=line['product_brand'],
            category_name=line['category_name'],
            store_name=line['store_name'],
            quantity=line['quantity'],
            unit_price=line['unit_price'],
            line_total=line['line_total'],
        )
        for line in snapshot['lines']
    ])

    clear_user_cart(user)
    return Order.objects.select_related('address').prefetch_related('items').get(id=order.id)
