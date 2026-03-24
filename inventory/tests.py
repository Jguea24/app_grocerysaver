"""Tests del dominio de inventario."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from alerts.models import Alert, AlertStatus, AlertType
from grocerysaver.models import Category, Product, ProductPrice, Role, Store, UserProfile
from inventory.models import InventoryItem
from inventory.services import seed_demo_expiring_inventory_for_user


class InventoryEndpointTests(APITestCase):
    """Valida altas y cambios basicos del inventario con alertas."""

    def setUp(self):
        self.role, _ = Role.objects.get_or_create(name='cliente')
        self.user = get_user_model().objects.create_user(
            username='inventory.user',
            email='inventory@example.com',
            password='TestPass123!@#',
            is_active=True,
        )
        UserProfile.objects.create(
            user=self.user,
            role=self.role,
            address='Centro',
            birth_date='1990-01-01',
        )
        self.client.force_authenticate(self.user)

        self.category, _ = Category.objects.get_or_create(name='Despensa')
        self.product = Product.objects.create(category=self.category, name='Arroz', brand='GrocerySaver')
        self.store, _ = Store.objects.get_or_create(name='Supermaxi')
        ProductPrice.objects.create(product=self.product, store=self.store, price='2.55')

    def test_create_inventory_item_generates_expiry_alert(self):
        expires_at = timezone.localdate() + timedelta(days=2)

        response = self.client.post(
            '/api/inventory/items/',
            {
                'product_id': self.product.id,
                'quantity': 3,
                'expires_at': expires_at.isoformat(),
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['item']['quantity'], 3)
        self.assertEqual(response.data['item']['best_price'], '2.55')

        alert = Alert.objects.get(inventory_item_id=response.data['item']['id'])
        self.assertEqual(alert.type, AlertType.EXPIRY)
        self.assertEqual(alert.status, AlertStatus.ACTIVE)
        self.assertEqual(alert.days_remaining, 2)

    def test_updating_inventory_item_to_far_future_resolves_active_alert(self):
        expires_at = timezone.localdate() + timedelta(days=1)
        create_response = self.client.post(
            '/api/inventory/items/',
            {
                'product_id': self.product.id,
                'quantity': 1,
                'expires_at': expires_at.isoformat(),
            },
            format='json',
        )
        item_id = create_response.data['item']['id']

        update_response = self.client.patch(
            f'/api/inventory/items/{item_id}/',
            {
                'quantity': 2,
                'expires_at': (timezone.localdate() + timedelta(days=10)).isoformat(),
            },
            format='json',
        )

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data['item']['quantity'], 2)

        alert = Alert.objects.get(inventory_item_id=item_id)
        self.assertEqual(alert.status, AlertStatus.RESOLVED)


class DemoInventorySeedingTests(APITestCase):
    """Comprueba la carga automatica de inventario demo por caducar."""

    def setUp(self):
        self.role, _ = Role.objects.get_or_create(name='cliente')
        self.category, _ = Category.objects.get_or_create(name='Demo Caducidad')
        for product_name in [
            'Leche Entera 1L',
            'Manzana Roja',
            'Filete de Pescado 1kg',
            'Tomate',
            'Pechuga de Pollo 1kg',
        ]:
            Product.objects.get_or_create(category=self.category, name=product_name, defaults={'brand': 'Demo'})

    @override_settings(AUTO_SEED_EXPIRING_INVENTORY=True)
    def test_seed_demo_expiring_inventory_creates_items_and_alerts(self):
        user = get_user_model().objects.create_user(
            username='demo.seed',
            email='demo-seed@example.com',
            password='TestPass123!@#',
            is_active=True,
        )
        UserProfile.objects.create(
            user=user,
            role=self.role,
            address='Centro',
            birth_date='1990-01-01',
        )

        seeded_items = seed_demo_expiring_inventory_for_user(user)

        self.assertEqual(len(seeded_items), 5)
        self.assertEqual(InventoryItem.objects.filter(user=user).count(), 5)
        self.assertEqual(Alert.objects.filter(user=user, status=AlertStatus.ACTIVE).count(), 5)

    @override_settings(AUTO_SEED_EXPIRING_INVENTORY=True, AUTO_VERIFY_EMAIL_ON_REGISTER=True)
    def test_register_auto_seeds_demo_inventory_for_new_users(self):
        response = self.client.post(
            '/api/auth/register/',
            {
                'username': 'auto.alerts',
                'email': 'auto-alerts@example.com',
                'password': 'TestPass123!@#',
                'confirm_password': 'TestPass123!@#',
                'first_name': 'Auto',
                'role': 'cliente',
                'address': 'Centro',
                'birth_date': '1998-04-12',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = get_user_model().objects.get(email='auto-alerts@example.com')
        self.assertEqual(InventoryItem.objects.filter(user=user).count(), 5)
        self.assertEqual(Alert.objects.filter(user=user, status=AlertStatus.ACTIVE).count(), 5)


