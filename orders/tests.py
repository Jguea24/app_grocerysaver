"""Tests del dominio de ordenes."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from grocerysaver.models import Address, Cart, CartItem, Category, Product, ProductPrice, Role, Store, UserProfile

from .models import CheckoutStatus, Order, OrderStatus, PaymentStatus, ShipmentStatus


class CheckoutFlowTests(APITestCase):
    """Valida el flujo de checkout previo a pago y orden."""

    def setUp(self):
        self.role, _ = Role.objects.get_or_create(name='cliente')
        self.user = get_user_model().objects.create_user(username='checkout.user', email='checkout@example.com', password='TestPass123!@#', is_active=True)
        UserProfile.objects.create(user=self.user, role=self.role, address='Centro', birth_date='1990-01-01')
        self.client.force_authenticate(self.user)

        self.address = Address.objects.create(user=self.user, label='Casa', contact_name='Johnny Grefa', phone='0999999999', line1='Av. Principal 123', city='Quito', is_default=True)

        self.category = Category.objects.create(name='Checkout Test')
        self.store = Store.objects.create(name='Tienda Checkout')
        self.product = Product.objects.create(category=self.category, name='Arroz checkout', brand='GS')
        self.other_product = Product.objects.create(category=self.category, name='Azucar checkout', brand='GS')
        ProductPrice.objects.create(product=self.product, store=self.store, price='2.50')
        ProductPrice.objects.create(product=self.other_product, store=self.store, price='1.25')

        self.cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=self.cart, product=self.product, store=self.store, quantity=2)
        CartItem.objects.create(cart=self.cart, product=self.other_product, store=self.store, quantity=3)

    def test_create_checkout_from_cart_snapshots_items_and_keeps_cart(self):
        response = self.client.post('/api/checkout/', {'notes': 'Checkout inicial'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['checkout']['status'], CheckoutStatus.OPEN)
        self.assertEqual(response.data['checkout']['total_items'], 5)
        self.assertEqual(response.data['checkout']['subtotal'], '8.75')
        self.assertEqual(len(response.data['checkout']['items']), 2)
        self.assertEqual(CartItem.objects.filter(cart=self.cart).count(), 2)

    def test_patch_checkout_assigns_address_and_marks_ready_for_payment(self):
        create_response = self.client.post('/api/checkout/', {}, format='json')
        checkout_id = create_response.data['checkout']['id']

        response = self.client.patch(f'/api/checkout/{checkout_id}/', {'address_id': self.address.id, 'notes': 'Dejar en recepcion'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['checkout']['status'], CheckoutStatus.READY_FOR_PAYMENT)
        self.assertEqual(response.data['checkout']['address_snapshot']['city'], 'Quito')
        self.assertEqual(response.data['checkout']['notes'], 'Dejar en recepcion')

    def test_create_checkout_rejects_empty_cart(self):
        self.cart.items.all().delete()
        response = self.client.post('/api/checkout/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('carrito', response.data['detail'].lower())


class PaymentFlowTests(APITestCase):
    """Valida el flujo checkout -> payment -> order."""

    def setUp(self):
        self.role, _ = Role.objects.get_or_create(name='cliente')
        self.user = get_user_model().objects.create_user(username='payment.user', email='payment@example.com', password='TestPass123!@#', is_active=True)
        UserProfile.objects.create(user=self.user, role=self.role, address='Centro', birth_date='1990-01-01')
        self.client.force_authenticate(self.user)

        self.address = Address.objects.create(user=self.user, label='Casa', contact_name='Johnny Grefa', phone='0999999999', line1='Av. Principal 123', city='Quito', is_default=True)

        self.category = Category.objects.create(name='Payment Test')
        self.store = Store.objects.create(name='Tienda Payment')
        self.product = Product.objects.create(category=self.category, name='Arroz payment', brand='GS')
        ProductPrice.objects.create(product=self.product, store=self.store, price='2.50')

        self.cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=self.cart, product=self.product, store=self.store, quantity=2)

    def _create_ready_checkout(self):
        create_response = self.client.post('/api/checkout/', {}, format='json')
        checkout_id = create_response.data['checkout']['id']
        self.client.patch(f'/api/checkout/{checkout_id}/', {'address_id': self.address.id}, format='json')
        return checkout_id

    def test_process_payment_converts_checkout_into_placed_order_and_shipment(self):
        checkout_id = self._create_ready_checkout()

        response = self.client.post('/api/payments/', {'checkout_id': checkout_id, 'method': 'card'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['payment']['status'], PaymentStatus.SUCCEEDED)
        self.assertIsNotNone(response.data['order'])
        self.assertEqual(response.data['order']['status'], OrderStatus.PLACED)
        self.assertEqual(response.data['order']['checkout_id'], checkout_id)
        self.assertIsNotNone(response.data['shipment'])
        self.assertEqual(response.data['shipment']['status'], ShipmentStatus.PENDING)
        self.assertEqual(CartItem.objects.filter(cart=self.cart).count(), 0)

    def test_payment_rejects_checkout_without_address(self):
        create_response = self.client.post('/api/checkout/', {}, format='json')
        checkout_id = create_response.data['checkout']['id']

        response = self.client.post('/api/payments/', {'checkout_id': checkout_id, 'method': 'card'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('listo para pago', response.data['detail'].lower())

    def test_payment_simulated_failure_keeps_checkout_ready(self):
        checkout_id = self._create_ready_checkout()

        response = self.client.post('/api/payments/', {'checkout_id': checkout_id, 'method': 'card', 'simulate_failure': True}, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['payment']['status'], PaymentStatus.FAILED)
        self.assertIsNone(response.data['order'])
        self.assertIsNone(response.data['shipment'])
        self.assertEqual(CartItem.objects.filter(cart=self.cart).count(), 1)


class ShipmentFlowTests(APITestCase):
    """Valida el flujo logistico posterior al pago."""

    def setUp(self):
        self.role, _ = Role.objects.get_or_create(name='cliente')
        self.user = get_user_model().objects.create_user(username='shipment.user', email='shipment@example.com', password='TestPass123!@#', is_active=True)
        UserProfile.objects.create(user=self.user, role=self.role, address='Centro', birth_date='1990-01-01')
        self.client.force_authenticate(self.user)

        self.address = Address.objects.create(user=self.user, label='Casa', contact_name='Johnny Grefa', phone='0999999999', line1='Av. Principal 123', city='Quito', is_default=True)

        self.category = Category.objects.create(name='Shipment Test')
        self.store = Store.objects.create(name='Tienda Shipment')
        self.product = Product.objects.create(category=self.category, name='Arroz shipment', brand='GS')
        ProductPrice.objects.create(product=self.product, store=self.store, price='2.50')

        self.cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=self.cart, product=self.product, store=self.store, quantity=2)

        create_response = self.client.post('/api/checkout/', {}, format='json')
        self.checkout_id = create_response.data['checkout']['id']
        self.client.patch(f'/api/checkout/{self.checkout_id}/', {'address_id': self.address.id}, format='json')
        payment_response = self.client.post('/api/payments/', {'checkout_id': self.checkout_id, 'method': 'card'}, format='json')
        self.shipment_id = payment_response.data['shipment']['id']
        self.order_id = payment_response.data['order']['id']

    def test_list_shipments_only_returns_current_user_shipments(self):
        other_user = get_user_model().objects.create_user(username='other.shipment', email='other-shipment@example.com', password='TestPass123!@#', is_active=True)
        UserProfile.objects.create(user=other_user, role=self.role, address='Sur', birth_date='1991-01-01')
        other_address = Address.objects.create(user=other_user, label='Casa', contact_name='Otra Persona', phone='0888888888', line1='Calle Secundaria', city='Cuenca', is_default=True)
        other_cart = Cart.objects.create(user=other_user)
        CartItem.objects.create(cart=other_cart, product=self.product, store=self.store, quantity=1)

        self.client.force_authenticate(other_user)
        checkout_response = self.client.post('/api/checkout/', {}, format='json')
        checkout_id = checkout_response.data['checkout']['id']
        self.client.patch(f'/api/checkout/{checkout_id}/', {'address_id': other_address.id}, format='json')
        self.client.post('/api/payments/', {'checkout_id': checkout_id, 'method': 'card'}, format='json')

        self.client.force_authenticate(self.user)
        response = self.client.get('/api/shipments/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['shipments']), 1)
        self.assertEqual(response.data['shipments'][0]['order_id'], self.order_id)

    def test_patch_shipment_status_tracks_shipped_and_delivered_timestamps(self):
        preparing_response = self.client.patch(
            f'/api/shipments/{self.shipment_id}/',
            {'status': ShipmentStatus.PREPARING, 'notes': 'Empacando pedido'},
            format='json',
        )
        self.assertEqual(preparing_response.status_code, status.HTTP_200_OK)
        self.assertEqual(preparing_response.data['shipment']['status'], ShipmentStatus.PREPARING)

        shipped_response = self.client.patch(
            f'/api/shipments/{self.shipment_id}/',
            {
                'status': ShipmentStatus.SHIPPED,
                'carrier': 'Servientrega',
                'tracking_number': 'GS-TRACK-001',
            },
            format='json',
        )
        self.assertEqual(shipped_response.status_code, status.HTTP_200_OK)
        self.assertEqual(shipped_response.data['shipment']['status'], ShipmentStatus.SHIPPED)
        self.assertEqual(shipped_response.data['shipment']['carrier'], 'Servientrega')
        self.assertEqual(shipped_response.data['shipment']['tracking_number'], 'GS-TRACK-001')
        self.assertIsNotNone(shipped_response.data['shipment']['shipped_at'])

        delivered_response = self.client.patch(
            f'/api/shipments/{self.shipment_id}/',
            {'status': ShipmentStatus.DELIVERED},
            format='json',
        )
        self.assertEqual(delivered_response.status_code, status.HTTP_200_OK)
        self.assertEqual(delivered_response.data['shipment']['status'], ShipmentStatus.DELIVERED)
        self.assertIsNotNone(delivered_response.data['shipment']['delivered_at'])

    def test_patch_shipment_rejects_invalid_transition(self):
        response = self.client.patch(
            f'/api/shipments/{self.shipment_id}/',
            {'status': ShipmentStatus.DELIVERED},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('no se puede cambiar', response.data['detail'].lower())


class OrderFlowTests(APITestCase):
    """Valida la conversion del carrito a una orden pendiente de pago."""

    def setUp(self):
        self.role, _ = Role.objects.get_or_create(name='cliente')
        self.user = get_user_model().objects.create_user(username='orders.user', email='orders@example.com', password='TestPass123!@#', is_active=True)
        UserProfile.objects.create(user=self.user, role=self.role, address='Centro', birth_date='1990-01-01')
        self.client.force_authenticate(self.user)

        self.address = Address.objects.create(user=self.user, label='Casa', contact_name='Johnny Grefa', phone='0999999999', line1='Av. Principal 123', city='Quito', is_default=True)

        self.category = Category.objects.create(name='Ordenes Test')
        self.store = Store.objects.create(name='Tienda Ordenes')
        self.product = Product.objects.create(category=self.category, name='Arroz orden', brand='GS')
        self.other_product = Product.objects.create(category=self.category, name='Azucar orden', brand='GS')
        ProductPrice.objects.create(product=self.product, store=self.store, price='2.50')
        ProductPrice.objects.create(product=self.other_product, store=self.store, price='1.25')

        self.cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=self.cart, product=self.product, store=self.store, quantity=2)
        CartItem.objects.create(cart=self.cart, product=self.other_product, store=self.store, quantity=3)

    def test_create_order_from_cart_snapshots_items_and_clears_cart(self):
        response = self.client.post('/api/orders/', {'address_id': self.address.id, 'notes': 'Entrega en horario de oficina'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['order']['status'], OrderStatus.PENDING_PAYMENT)
        self.assertEqual(response.data['order']['total_items'], 5)
        self.assertEqual(response.data['order']['subtotal'], '8.75')
        self.assertEqual(len(response.data['order']['items']), 2)
        self.assertEqual(CartItem.objects.filter(cart=self.cart).count(), 0)

        order = Order.objects.get(id=response.data['order']['id'])
        self.assertEqual(order.contact_name, 'Johnny Grefa')
        self.assertEqual(order.city, 'Quito')
        self.assertEqual(order.total, Decimal('8.75'))

    def test_create_order_rejects_empty_cart(self):
        self.cart.items.all().delete()
        response = self.client.post('/api/orders/', {'address_id': self.address.id}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('carrito', response.data['detail'].lower())

    def test_list_orders_only_returns_current_user_orders(self):
        self.client.post('/api/orders/', {'address_id': self.address.id}, format='json')

        other_user = get_user_model().objects.create_user(username='other.orders', email='other-orders@example.com', password='TestPass123!@#', is_active=True)
        UserProfile.objects.create(user=other_user, role=self.role, address='Sur', birth_date='1991-01-01')
        other_address = Address.objects.create(user=other_user, label='Casa', contact_name='Otra Persona', phone='0888888888', line1='Calle Secundaria', city='Cuenca', is_default=True)
        other_cart = Cart.objects.create(user=other_user)
        CartItem.objects.create(cart=other_cart, product=self.product, store=self.store, quantity=1)

        self.client.force_authenticate(other_user)
        self.client.post('/api/orders/', {'address_id': other_address.id}, format='json')

        self.client.force_authenticate(self.user)
        response = self.client.get('/api/orders/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['orders']), 1)
        self.assertEqual(response.data['orders'][0]['address_snapshot']['city'], 'Quito')
