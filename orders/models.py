"""Modelos del dominio de ordenes."""

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models


class CheckoutStatus(models.TextChoices):
    """Estados base del ciclo de vida de una sesion de checkout."""

    OPEN = 'open', 'Open'
    READY_FOR_PAYMENT = 'ready_for_payment', 'Ready for payment'
    CONVERTED = 'converted', 'Converted'
    EXPIRED = 'expired', 'Expired'
    CANCELLED = 'cancelled', 'Cancelled'


class OrderStatus(models.TextChoices):
    """Estados base del ciclo de vida de una orden."""

    PENDING_PAYMENT = 'pending_payment', 'Pending payment'
    PLACED = 'placed', 'Placed'
    CANCELLED = 'cancelled', 'Cancelled'


class PaymentStatus(models.TextChoices):
    """Estados basicos del procesamiento de pago."""

    PENDING = 'pending', 'Pending'
    SUCCEEDED = 'succeeded', 'Succeeded'
    FAILED = 'failed', 'Failed'


class PaymentMethod(models.TextChoices):
    """Metodos de pago soportados por el backend actual."""

    CARD = 'card', 'Card'
    CASH = 'cash', 'Cash'
    TRANSFER = 'transfer', 'Transfer'


class ShipmentStatus(models.TextChoices):
    """Estados del flujo logistico posterior al pago."""

    PENDING = 'pending', 'Pending'
    PREPARING = 'preparing', 'Preparing'
    SHIPPED = 'shipped', 'Shipped'
    DELIVERED = 'delivered', 'Delivered'
    CANCELLED = 'cancelled', 'Cancelled'


class CheckoutSession(models.Model):
    """Snapshot intermedio del carrito antes de confirmar pago y crear orden."""

    checkout_number = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='checkout_sessions')
    address = models.ForeignKey('grocerysaver.Address', on_delete=models.SET_NULL, related_name='checkout_sessions', null=True, blank=True)
    status = models.CharField(max_length=30, choices=CheckoutStatus.choices, default=CheckoutStatus.OPEN)
    address_label = models.CharField(max_length=50, blank=True)
    contact_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    line1 = models.CharField(max_length=255, blank=True)
    line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    total_items = models.PositiveIntegerField(default=0)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [models.Index(fields=['user', 'status', '-created_at'])]

    def __str__(self):
        return f'CheckoutSession(user={self.user_id}, checkout_number={self.checkout_number}, status={self.status})'


class CheckoutItem(models.Model):
    """Snapshot de cada linea incluida en una sesion de checkout."""

    checkout = models.ForeignKey(CheckoutSession, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('grocerysaver.Product', on_delete=models.SET_NULL, related_name='checkout_items', null=True, blank=True)
    store = models.ForeignKey('grocerysaver.Store', on_delete=models.SET_NULL, related_name='checkout_items', null=True, blank=True)
    product_name = models.CharField(max_length=120)
    product_brand = models.CharField(max_length=120, blank=True)
    category_name = models.CharField(max_length=80, blank=True)
    store_name = models.CharField(max_length=80, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f'CheckoutItem(checkout={self.checkout_id}, product={self.product_name}, quantity={self.quantity})'


class Order(models.Model):
    """Snapshot de una compra confirmada a partir del carrito del usuario."""

    order_number = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders')
    checkout = models.ForeignKey(CheckoutSession, on_delete=models.SET_NULL, related_name='orders', null=True, blank=True)
    address = models.ForeignKey('grocerysaver.Address', on_delete=models.SET_NULL, related_name='orders', null=True, blank=True)
    status = models.CharField(max_length=30, choices=OrderStatus.choices, default=OrderStatus.PENDING_PAYMENT)
    address_label = models.CharField(max_length=50, blank=True)
    contact_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30)
    line1 = models.CharField(max_length=255)
    line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    notes = models.CharField(max_length=255, blank=True)
    total_items = models.PositiveIntegerField(default=0)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [models.Index(fields=['user', 'status', '-created_at'])]

    def __str__(self):
        return f'Order(user={self.user_id}, order_number={self.order_number}, status={self.status})'


class OrderItem(models.Model):
    """Snapshot de cada linea comprada dentro de una orden."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('grocerysaver.Product', on_delete=models.SET_NULL, related_name='order_items', null=True, blank=True)
    store = models.ForeignKey('grocerysaver.Store', on_delete=models.SET_NULL, related_name='order_items', null=True, blank=True)
    product_name = models.CharField(max_length=120)
    product_brand = models.CharField(max_length=120, blank=True)
    category_name = models.CharField(max_length=80, blank=True)
    store_name = models.CharField(max_length=80, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f'OrderItem(order={self.order_id}, product={self.product_name}, quantity={self.quantity})'


class Payment(models.Model):
    """Pago procesado sobre un checkout y asociado a una orden si fue exitoso."""

    payment_number = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payments')
    checkout = models.ForeignKey(CheckoutSession, on_delete=models.CASCADE, related_name='payments')
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, related_name='payments', null=True, blank=True)
    method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    provider = models.CharField(max_length=50, default='sandbox')
    status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='USD')
    provider_reference = models.CharField(max_length=120, blank=True)
    failure_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [models.Index(fields=['user', 'status', '-created_at']), models.Index(fields=['checkout', 'status'])]

    def __str__(self):
        return f'Payment(user={self.user_id}, payment_number={self.payment_number}, status={self.status})'


class Shipment(models.Model):
    """Envio asociado a una orden pagada."""

    shipment_number = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='shipments')
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='shipment')
    status = models.CharField(max_length=20, choices=ShipmentStatus.choices, default=ShipmentStatus.PENDING)
    carrier = models.CharField(max_length=80, blank=True)
    tracking_number = models.CharField(max_length=120, blank=True)
    contact_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30)
    line1 = models.CharField(max_length=255)
    line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    notes = models.CharField(max_length=255, blank=True)
    estimated_delivery_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [models.Index(fields=['user', 'status', '-created_at']), models.Index(fields=['order'])]

    def __str__(self):
        return f'Shipment(user={self.user_id}, shipment_number={self.shipment_number}, status={self.status})'
