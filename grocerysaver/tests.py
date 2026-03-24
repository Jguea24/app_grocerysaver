"""Tests de integracion para auth, catalogo, cache, DataLoader y jobs."""

import os
import shutil
import tempfile
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIRequestFactory, APITestCase

from .models import (
    Address,
    BackgroundJob,
    Cart,
    CartItem,
    Category,
    DeviceSensorReading,
    EmailVerificationToken,
    NotificationPreference,
    Offer,
    Product,
    ProductCode,
    ProductPrice,
    Raffle,
    Role,
    RoleChangeRequest,
    SocialAccount,
    Store,
    UserProfile,
)
from .job_queue import process_next_job
from .serializers import ProductSerializer


class AuthFlowTests(APITestCase):
    """Casos de autenticacion, verificacion y permisos basicos."""

    def setUp(self):
        self.cliente_role, _ = Role.objects.get_or_create(
            name='cliente',
            defaults={'description': 'Cliente de la aplicacion'},
        )
        self.admin_role, _ = Role.objects.get_or_create(
            name='admin',
            defaults={'description': 'Administrador de la aplicacion'},
        )

    @override_settings(AUTO_VERIFY_EMAIL_ON_REGISTER=False)
    def test_register_verify_and_login_with_role(self):
        register_response = self.client.post(
            '/api/auth/register/',
            {
                'username': 'ana.user',
                'email': 'ana@example.com',
                'password': 'TestPass123!@#',
                'confirm_password': 'TestPass123!@#',
                'first_name': 'Ana',
                'role': 'cliente',
                'address': 'Av. Siempre Viva 123',
                'birth_date': '1998-04-12',
            },
            format='json',
        )
        self.assertEqual(register_response.status_code, status.HTTP_201_CREATED)

        user_model = get_user_model()
        user = user_model.objects.get(email='ana@example.com')
        profile = UserProfile.objects.get(user=user)
        self.assertFalse(user.is_active)
        self.assertEqual(profile.role.name, 'cliente')

        verification = EmailVerificationToken.objects.get(user=user)
        verify_response = self.client.post(
            '/api/auth/verify-email/',
            {'token': str(verification.token)},
            format='json',
        )
        self.assertEqual(verify_response.status_code, status.HTTP_200_OK)
        self.assertEqual(verify_response.data['user']['role'], 'cliente')

        login_response = self.client.post(
            '/api/auth/login/',
            {'email': 'ana@example.com', 'password': 'TestPass123!@#'},
            format='json',
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertIn('tokens', login_response.data)
        self.assertEqual(login_response.data['user']['role'], 'cliente')

    def test_register_requires_role(self):
        response = self.client.post(
            '/api/auth/register/',
            {
                'email': 'missing@example.com',
                'password': 'TestPass123!@#',
                'confirm_password': 'TestPass123!@#',
                'address': 'Quito',
                'birth_date': '1995-01-01',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('role', response.data)

    def test_protected_route_rejects_unauthenticated(self):
        response = self.client.get('/api/protected/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @override_settings(AUTO_VERIFY_EMAIL_ON_REGISTER=False)
    def test_me_protected_and_logout(self):
        register_response = self.client.post(
            '/api/auth/register/',
            {
                'username': 'cam.user',
                'email': 'cam@example.com',
                'password': 'TestPass123!@#',
                'confirm_password': 'TestPass123!@#',
                'first_name': 'Cam',
                'role': 'cliente',
                'address': 'Centro',
                'birth_date': '1997-03-10',
            },
            format='json',
        )
        self.assertEqual(register_response.status_code, status.HTTP_201_CREATED)

        user_model = get_user_model()
        user = user_model.objects.get(email='cam@example.com')
        verification = EmailVerificationToken.objects.get(user=user)
        self.client.post('/api/auth/verify-email/', {'token': str(verification.token)}, format='json')

        login_response = self.client.post(
            '/api/auth/login/',
            {'email': 'cam@example.com', 'password': 'TestPass123!@#'},
            format='json',
        )
        access = login_response.data['tokens']['access']
        refresh = login_response.data['tokens']['refresh']

        me_response = self.client.get(
            '/api/auth/me/',
            HTTP_AUTHORIZATION=f'Bearer {access}',
        )
        self.assertEqual(me_response.status_code, status.HTTP_200_OK)
        self.assertEqual(me_response.data['user']['email'], 'cam@example.com')

        protected_response = self.client.get(
            '/api/protected/',
            HTTP_AUTHORIZATION=f'Bearer {access}',
        )
        self.assertEqual(protected_response.status_code, status.HTTP_200_OK)

        logout_response = self.client.post(
            '/api/auth/logout/',
            {'refresh': refresh},
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {access}',
        )
        self.assertEqual(logout_response.status_code, status.HTTP_200_OK)

        logout_again_response = self.client.post(
            '/api/auth/logout/',
            {'refresh': refresh},
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {access}',
        )
        self.assertEqual(logout_again_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_auto_verifies_user_when_setting_enabled(self):
        response = self.client.post(
            '/api/auth/register/',
            {
                'username': 'auto.user',
                'email': 'auto@example.com',
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
        self.assertEqual(response.data['email_verification_required'], False)

        user = get_user_model().objects.get(email='auto@example.com')
        self.assertTrue(user.is_active)
        self.assertFalse(EmailVerificationToken.objects.filter(user=user).exists())

    def test_admin_only_route_uses_role(self):
        user_model = get_user_model()
        customer = user_model.objects.create_user(
            username='customer.user',
            email='customer@example.com',
            password='TestPass123!@#',
            is_active=True,
        )
        UserProfile.objects.create(
            user=customer,
            role=self.cliente_role,
            address='Norte',
            birth_date='1995-06-22',
        )

        admin_user = user_model.objects.create_user(
            username='admin.user',
            email='admin@example.com',
            password='TestPass123!@#',
            is_active=True,
        )
        UserProfile.objects.create(
            user=admin_user,
            role=self.admin_role,
            address='Sur',
            birth_date='1990-11-05',
        )

        customer_login = self.client.post(
            '/api/auth/login/',
            {'email': 'customer@example.com', 'password': 'TestPass123!@#'},
            format='json',
        )
        customer_access = customer_login.data['tokens']['access']
        customer_response = self.client.get(
            '/api/protected/admin-only/',
            HTTP_AUTHORIZATION=f'Bearer {customer_access}',
        )
        self.assertEqual(customer_response.status_code, status.HTTP_403_FORBIDDEN)

        admin_login = self.client.post(
            '/api/auth/login/',
            {'email': 'admin@example.com', 'password': 'TestPass123!@#'},
            format='json',
        )
        admin_access = admin_login.data['tokens']['access']
        admin_response = self.client.get(
            '/api/protected/admin-only/',
            HTTP_AUTHORIZATION=f'Bearer {admin_access}',
        )
        self.assertEqual(admin_response.status_code, status.HTTP_200_OK)

    @patch('grocerysaver.views.verify_google_id_token')
    def test_social_login_creates_user_and_account(self, mocked_verify_google_id_token):
        mocked_verify_google_id_token.return_value = {
            'provider_user_id': 'google-123',
            'email': 'social@example.com',
            'first_name': 'Social',
            'last_name': '',
        }

        response = self.client.post(
            '/api/auth/social-login/',
            {
                'provider': 'google',
                'id_token': 'google-id-token',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['created'])

        user_model = get_user_model()
        user = user_model.objects.get(email='social@example.com')
        self.assertTrue(user.is_active)
        self.assertTrue(
            SocialAccount.objects.filter(
                user=user,
                provider='google',
                provider_user_id='google-123',
            ).exists()
        )

    def test_social_login_requires_id_token(self):
        response = self.client.post(
            '/api/auth/social-login/',
            {
                'provider': 'google',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('id_token', response.data)


class CatalogComparisonTests(APITestCase):
    """Pruebas del catalogo publico y comparacion de precios."""

    def setUp(self):
        cache.clear()

    def test_store_category_and_product_list_endpoints(self):
        stores_response = self.client.get('/api/stores/')
        self.assertEqual(stores_response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(stores_response.data['stores']), 3)

        categories_response = self.client.get('/api/categories/')
        self.assertEqual(categories_response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(categories_response.data['categories']), 5)

        products_response = self.client.get('/api/products/')
        self.assertEqual(products_response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(products_response.data['products']), 5)

    def test_compare_prices_for_leche(self):
        product = Product.objects.filter(name__icontains='Leche').first()
        self.assertIsNotNone(product)

        response = self.client.get(f'/api/compare-prices/?product_id={product.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['stores_available'], 3)
        self.assertEqual(response.data['best_option']['store'], 'Toti')
        self.assertEqual(response.data['best_option']['price'], '1.05')
        self.assertEqual(response.data['most_expensive_option']['store'], 'Tia')
        self.assertEqual(response.data['most_expensive_option']['price'], '2.25')
        self.assertEqual(response.data['savings_vs_most_expensive'], '1.20')


class ProductScanEndpointTests(APITestCase):
    """Cobertura del endpoint de escaneo y alta rapida de productos."""

    def setUp(self):
        cache.clear()
        self.category = Category.objects.create(name='Enlatados')
        self.store = Store.objects.create(name='Mi Comisariato')
        self.product = Product.objects.create(
            category=self.category,
            name='Atun en agua',
            brand='Mar Azul',
            description='Lata de atun 140g',
        )
        ProductCode.objects.create(product=self.product, code='7501234567890', code_type='barcode')
        ProductPrice.objects.create(product=self.product, store=self.store, price='2.10')

    def test_scan_returns_existing_product(self):
        response = self.client.post(
            '/api/products/scan/',
            {'code': '7501234567890'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['matched'])
        self.assertEqual(response.data['product']['name'], 'Atun en agua')
        self.assertEqual(response.data['scanned_code']['code'], '7501234567890')

    def test_scan_unknown_code_requires_minimum_fields(self):
        response = self.client.post(
            '/api/products/scan/',
            {'code': '998877665544'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('category_id y name', response.data['detail'])

    def test_scan_unknown_code_creates_product_and_price(self):
        response = self.client.post(
            '/api/products/scan/',
            {
                'code': '998877665544',
                'code_type': 'barcode',
                'category_id': self.category.id,
                'name': 'Sardina en tomate',
                'brand': 'Costa',
                'description': 'Lata 155g',
                'store_id': self.store.id,
                'price': '1.65',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data['matched'])
        self.assertTrue(response.data['product_created'])
        self.assertTrue(response.data['code_created'])
        self.assertTrue(response.data['price_updated'])
        self.assertTrue(ProductCode.objects.filter(code='998877665544').exists())


class OfferEndpointTests(APITestCase):
    """Validaciones del filtro de ofertas activas e historicas."""

    def setUp(self):
        cache.clear()
        self.category = Category.objects.create(name='Lacteos Test Offers')
        self.product = Product.objects.create(
            category=self.category,
            name='Yogurt Natural',
            brand='La Vaquita',
            description='Yogurt natural 1L',
        )
        self.store = Store.objects.create(name='SuperMaxi')
        now = timezone.now()

        Offer.objects.create(
            product=self.product,
            store=self.store,
            normal_price='2.50',
            offer_price='1.99',
            starts_at=now - timedelta(days=1),
            ends_at=now + timedelta(days=1),
        )
        Offer.objects.create(
            product=self.product,
            store=self.store,
            normal_price='2.60',
            offer_price='2.20',
            starts_at=now - timedelta(days=10),
            ends_at=now - timedelta(days=5),
        )

    def test_offers_returns_only_active_by_default(self):
        response = self.client.get('/api/offers/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['offers'][0]['offer_price'], '1.99')
        self.assertEqual(response.data['offers'][0]['is_active'], True)

    def test_offers_active_false_includes_expired(self):
        response = self.client.get('/api/offers/?active=false')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)


class ProfileMenuEndpointsTests(APITestCase):
    """Pruebas de endpoints de perfil autenticado."""

    def setUp(self):
        cache.clear()
        self.cliente_role, _ = Role.objects.get_or_create(name='cliente')
        self.admin_role, _ = Role.objects.get_or_create(name='admin')
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username='perfil.user',
            email='perfil@example.com',
            password='TestPass123!@#',
            is_active=True,
        )
        UserProfile.objects.create(
            user=self.user,
            role=self.cliente_role,
            address='Centro',
            birth_date='1996-08-15',
        )
        self.client.force_authenticate(user=self.user)

    def test_address_endpoints(self):
        create_response = self.client.post(
            '/api/profile/addresses/',
            {
                'label': 'Casa',
                'contact_name': 'Johnny Grefa',
                'phone': '0999999999',
                'line1': 'Av. Principal 123',
                'city': 'Quito',
                'is_default': True,
            },
            format='json',
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        list_response = self.client.get('/api/profile/addresses/')
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data['addresses']), 1)
        self.assertEqual(list_response.data['addresses'][0]['city'], 'Quito')

    def test_notification_preferences_endpoint(self):
        get_response = self.client.get('/api/profile/notifications/')
        self.assertEqual(get_response.status_code, status.HTTP_200_OK)
        self.assertTrue(get_response.data['notification_preferences']['push_enabled'])

        patch_response = self.client.patch(
            '/api/profile/notifications/',
            {'push_enabled': False, 'sms_enabled': True},
            format='json',
        )
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertFalse(patch_response.data['notification_preferences']['push_enabled'])
        self.assertTrue(patch_response.data['notification_preferences']['sms_enabled'])

        self.assertTrue(NotificationPreference.objects.filter(user=self.user).exists())

    def test_active_raffles_endpoint(self):
        now = timezone.now()
        Raffle.objects.create(
            title='Rifa activa',
            starts_at=now - timedelta(days=1),
            ends_at=now + timedelta(days=1),
        )
        Raffle.objects.create(
            title='Rifa finalizada',
            starts_at=now - timedelta(days=3),
            ends_at=now - timedelta(days=2),
        )

        response = self.client.get('/api/raffles/active/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['raffles']), 1)
        self.assertEqual(response.data['raffles'][0]['title'], 'Rifa activa')

    def test_role_change_request_endpoint(self):
        create_response = self.client.post(
            '/api/profile/role-change-requests/',
            {
                'requested_role': 'admin',
                'reason': 'Quiero gestionar el catalogo',
            },
            format='json',
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_response.data['request']['status'], 'pending')

        list_response = self.client.get('/api/profile/role-change-requests/')
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data['requests']), 1)

        self.assertTrue(
            RoleChangeRequest.objects.filter(
                user=self.user,
                requested_role=self.admin_role,
                status='pending',
            ).exists()
        )

    def test_only_owner_can_modify_address(self):
        other_user = get_user_model().objects.create_user(
            username='otro.user',
            email='otro@example.com',
            password='TestPass123!@#',
            is_active=True,
        )
        address = Address.objects.create(
            user=other_user,
            contact_name='Otro',
            phone='0988888888',
            line1='Otra calle',
            city='Loja',
            is_default=True,
        )

        response = self.client.patch(
            f'/api/profile/addresses/{address.id}/',
            {'city': 'Cuenca'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class CartEndpointTests(APITestCase):
    """Pruebas del carrito persistido y sus lineas CRUD."""

    def setUp(self):
        cache.clear()
        role, _ = Role.objects.get_or_create(name='cliente')
        self.user = get_user_model().objects.create_user(
            username='cart.user',
            email='cart@example.com',
            password='TestPass123!@#',
            is_active=True,
        )
        UserProfile.objects.create(
            user=self.user,
            role=role,
            address='Centro',
            birth_date='1994-02-10',
        )
        self.client.force_authenticate(user=self.user)

        self.category = Category.objects.create(name='Despensa Cart')
        self.product = Product.objects.create(
            category=self.category,
            name='Arroz extra',
            brand='Campos',
            description='Saco 1kg',
        )
        self.other_product = Product.objects.create(
            category=self.category,
            name='Azucar morena',
            brand='Dulce Vida',
            description='Funda 1kg',
        )
        self.store_expensive = Store.objects.create(name='Super Cart')
        self.store_best = Store.objects.create(name='Toti Cart')
        ProductPrice.objects.create(product=self.product, store=self.store_expensive, price='1.50')
        ProductPrice.objects.create(product=self.product, store=self.store_best, price='1.20')
        ProductPrice.objects.create(product=self.other_product, store=self.store_best, price='0.95')

    def test_get_cart_creates_empty_cart(self):
        response = self.client.get('/api/cart/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['cart']['items'], [])
        self.assertEqual(response.data['cart']['total_items'], 0)
        self.assertEqual(response.data['cart']['subtotal'], '0.00')
        self.assertTrue(Cart.objects.filter(user=self.user).exists())

    def test_add_cart_item_uses_best_price_store(self):
        response = self.client.post(
            '/api/cart/items/',
            {
                'product_id': self.product.id,
                'quantity': 2,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['item']['store']['name'], 'Toti Cart')
        self.assertEqual(response.data['item']['unit_price'], '1.20')
        self.assertEqual(response.data['cart']['total_items'], 2)
        self.assertEqual(response.data['cart']['subtotal'], '2.40')

    def test_add_same_product_merges_existing_item(self):
        self.client.post(
            '/api/cart/items/',
            {
                'product_id': self.product.id,
                'quantity': 1,
            },
            format='json',
        )

        response = self.client.post(
            '/api/cart/items/',
            {
                'product_id': self.product.id,
                'quantity': 2,
                'store_id': self.store_expensive.id,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(CartItem.objects.count(), 1)
        self.assertEqual(response.data['item']['quantity'], 3)
        self.assertEqual(response.data['item']['store']['name'], 'Super Cart')
        self.assertEqual(response.data['cart']['subtotal'], '4.50')

    def test_patch_cart_item_updates_quantity_and_store(self):
        create_response = self.client.post(
            '/api/cart/items/',
            {
                'product_id': self.product.id,
                'quantity': 1,
            },
            format='json',
        )
        item_id = create_response.data['item']['id']

        response = self.client.patch(
            f'/api/cart/items/{item_id}/',
            {
                'quantity': 4,
                'store_id': self.store_expensive.id,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['item']['quantity'], 4)
        self.assertEqual(response.data['item']['store']['name'], 'Super Cart')
        self.assertEqual(response.data['item']['line_total'], '6.00')
        self.assertEqual(response.data['cart']['subtotal'], '6.00')

    def test_delete_cart_item_and_clear_cart(self):
        first_response = self.client.post(
            '/api/cart/items/',
            {
                'product_id': self.product.id,
                'quantity': 1,
            },
            format='json',
        )
        self.client.post(
            '/api/cart/items/',
            {
                'product_id': self.other_product.id,
                'quantity': 3,
            },
            format='json',
        )

        item_id = first_response.data['item']['id']
        delete_response = self.client.delete(f'/api/cart/items/{item_id}/')
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(CartItem.objects.count(), 1)

        clear_response = self.client.delete('/api/cart/')
        self.assertEqual(clear_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(CartItem.objects.count(), 0)


class WeatherEndpointTests(APITestCase):
    """Cobertura del endpoint de clima y su cache."""

    def setUp(self):
        cache.clear()

    def test_weather_requires_city_or_coordinates(self):
        response = self.client.get('/api/weather/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('city o lat/lon', response.data['detail'])

    def test_weather_rejects_incomplete_coordinates(self):
        response = self.client.get('/api/weather/?lat=-0.99')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('lat y lon', response.data['detail'])

    @patch('grocerysaver.views.get_weather_payload')
    def test_weather_by_city(self, mocked_get_weather):
        mocked_get_weather.return_value = {
            'provider': 'open-meteo',
            'location': {'name': 'Tena'},
            'current': {'temperature_c': 17},
            'hourly': [],
            'daily': [],
        }

        response = self.client.get('/api/weather/?city=Tena')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['provider'], 'open-meteo')
        self.assertEqual(response.data['location']['name'], 'Tena')
        mocked_get_weather.assert_called_once_with(city='Tena', latitude=None, longitude=None)

    @patch('grocerysaver.views.get_weather_payload')
    def test_weather_by_coordinates(self, mocked_get_weather):
        mocked_get_weather.return_value = {
            'provider': 'open-meteo',
            'location': {'name': 'Coordenadas'},
            'current': {'temperature_c': 20},
            'hourly': [],
            'daily': [],
        }

        response = self.client.get('/api/weather/?lat=-0.99&lon=-77.81')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mocked_get_weather.assert_called_once_with(city=None, latitude=-0.99, longitude=-77.81)

    @patch('grocerysaver.views.get_weather_payload')
    def test_weather_cache_hits_for_same_query(self, mocked_get_weather):
        mocked_get_weather.return_value = {
            'provider': 'open-meteo',
            'location': {'name': 'Tena'},
            'current': {'temperature_c': 18},
            'hourly': [],
            'daily': [],
        }

        first_response = self.client.get('/api/weather/?city=Tena')
        second_response = self.client.get('/api/weather/?city=Tena')

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(first_response['X-Cache-Status'], 'MISS')
        self.assertEqual(second_response['X-Cache-Status'], 'HIT')
        mocked_get_weather.assert_called_once_with(city='Tena', latitude=None, longitude=None)


class CacheInvalidationTests(APITestCase):
    """Comprueba hit/miss e invalidacion de cache publico."""

    def setUp(self):
        cache.clear()

    def test_categories_cache_invalidates_after_catalog_change(self):
        Category.objects.create(name='Limpieza')

        first_response = self.client.get('/api/categories/')
        second_response = self.client.get('/api/categories/')

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(first_response['X-Cache-Status'], 'MISS')
        self.assertEqual(second_response['X-Cache-Status'], 'HIT')

        Category.objects.create(name='Mascotas')

        third_response = self.client.get('/api/categories/')
        self.assertEqual(third_response.status_code, status.HTTP_200_OK)
        self.assertEqual(third_response['X-Cache-Status'], 'MISS')
        self.assertTrue(any(category['name'] == 'Mascotas' for category in third_response.data['categories']))


class DataLoaderTests(APITestCase):
    """Verifica batching y cache por request del DataLoader."""

    def setUp(self):
        cache.clear()
        self.factory = APIRequestFactory()
        self.category = Category.objects.create(name='Bebidas calientes')

        for index in range(3):
            Product.objects.create(
                category=self.category,
                name=f'Café {index}',
                brand='Andes',
                description='Bolsa 250g',
            )

    def test_product_serializer_batches_and_caches_qr_codes_per_request(self):
        request = self.factory.get('/api/products/')
        products = list(
            Product.objects.select_related('category')
            .filter(category=self.category)
            .order_by('id')
        )

        with CaptureQueriesContext(connection) as context:
            first_payload = ProductSerializer(products, many=True, context={'request': request}).data
            second_payload = ProductSerializer(products, many=True, context={'request': request}).data

        product_code_queries = [
            query['sql']
            for query in context.captured_queries
            if 'grocerysaver_productcode' in query['sql'].lower()
        ]

        self.assertEqual(len(first_payload), 3)
        self.assertEqual(len(second_payload), 3)
        self.assertEqual(len(product_code_queries), 1)


class BackgroundJobEndpointTests(APITestCase):
    """Pruebas de la cola de trabajos y consulta de estado."""

    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(
            username='jobs.user',
            email='jobs@example.com',
            password='TestPass123!@#',
            is_active=True,
        )
        self.client.force_authenticate(user=self.user)

        category = Category.objects.create(name='Snacks')
        Product.objects.create(
            category=category,
            name='Papas clasicas',
            brand='Andinas',
            description='Bolsa 100g',
        )

    def test_enqueue_export_job_returns_accepted(self):
        response = self.client.post('/api/jobs/export-products/', {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data['job']['status'], 'queued')
        self.assertEqual(response.data['job']['payload']['format'], 'csv')
        self.assertEqual(BackgroundJob.objects.count(), 1)

    def test_job_detail_reports_completed_result(self):
        enqueue_response = self.client.post('/api/jobs/export-products/', {}, format='json')
        job_id = enqueue_response.data['job']['job_id']

        processed_job = process_next_job()
        self.assertIsNotNone(processed_job)
        self.assertEqual(processed_job.status, 'completed')

        detail_response = self.client.get(f'/api/jobs/{job_id}/')
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertTrue(detail_response.data['is_finished'])
        self.assertEqual(detail_response.data['job']['status'], 'completed')
        self.assertIn('file_name', detail_response.data['job']['result'])
        self.assertEqual(detail_response.data['job']['result']['file_format'], 'csv')

    def test_enqueue_export_job_accepts_txt_format(self):
        response = self.client.post(
            '/api/jobs/export-products/',
            {'format': 'txt', 'search': 'Papas'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data['job']['payload']['format'], 'txt')

    def test_job_detail_reports_completed_pdf_result(self):
        enqueue_response = self.client.post(
            '/api/jobs/export-products/',
            {'format': 'pdf'},
            format='json',
        )
        job_id = enqueue_response.data['job']['job_id']

        processed_job = process_next_job()
        self.assertIsNotNone(processed_job)
        self.assertEqual(processed_job.status, 'completed')
        self.assertEqual(processed_job.result['file_format'], 'pdf')
        self.assertTrue(processed_job.result['file_name'].endswith('.pdf'))

        detail_response = self.client.get(f'/api/jobs/{job_id}/')
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data['job']['result']['file_format'], 'pdf')
        self.assertTrue(detail_response.data['job']['result_url'].endswith('.pdf'))

    def test_job_processing_falls_back_when_media_export_dir_is_not_writable(self):
        self.client.post('/api/jobs/export-products/', {}, format='json')

        with patch('grocerysaver.job_queue.is_directory_writable', side_effect=[False, True]):
            processed_job = process_next_job()

        self.assertIsNotNone(processed_job)
        self.assertEqual(processed_job.status, 'completed')
        self.assertEqual(processed_job.result['file_format'], 'csv')


class DeviceSensorEndpointTests(APITestCase):
    """Verifica el endpoint de captura de sensores del dispositivo."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='sensor.user',
            email='sensor@example.com',
            password='TestPass123!@#',
            is_active=True,
        )

    def test_create_device_sensor_reading_requires_authentication(self):
        response = self.client.post(
            '/api/device-sensors/',
            {
                'accelerometer': {'x': 0.12, 'y': -0.03, 'z': 9.81},
                'gyroscope': {'x': 0.01, 'y': 0.00, 'z': -0.02},
                'is_shaking': False,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_device_sensor_reading_persists_payload(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            '/api/device-sensors/',
            {
                'accelerometer': {'x': 0.12, 'y': -0.03, 'z': 9.81},
                'gyroscope': {'x': 0.01, 'y': 0.00, 'z': -0.02},
                'is_shaking': True,
                'captured_at': '2026-03-13T15:30:00Z',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(DeviceSensorReading.objects.count(), 1)

        reading = DeviceSensorReading.objects.get()
        self.assertEqual(reading.user, self.user)
        self.assertTrue(reading.is_shaking)
        self.assertEqual(response.data['sensor_reading']['accelerometer']['x'], 0.12)
        self.assertEqual(response.data['sensor_reading']['gyroscope']['z'], -0.02)
        self.assertEqual(response.data['sensor_reading']['user_id'], self.user.id)

    def test_create_device_sensor_reading_rejects_missing_axes(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            '/api/device-sensors/',
            {
                'accelerometer': {'x': 0.12, 'y': -0.03},
                'gyroscope': {'x': 0.01, 'y': 0.00, 'z': -0.02},
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('accelerometer', response.data)


class ProfileAvatarEndpointTests(APITestCase):
    """Verifica subida y eliminacion de foto de perfil."""

    def setUp(self):
        media_base_dir = os.path.join(os.getcwd(), 'media')
        os.makedirs(media_base_dir, exist_ok=True)
        self.temp_media_root = tempfile.mkdtemp(dir=media_base_dir)
        self.override = override_settings(MEDIA_ROOT=self.temp_media_root)
        self.override.enable()

        self.user = get_user_model().objects.create_user(
            username='avatar.user',
            email='avatar@example.com',
            password='TestPass123!@#',
            is_active=True,
        )
        UserProfile.objects.create(
            user=self.user,
            role=None,
            address='Centro',
            birth_date='1999-01-01',
        )
        self.client.force_authenticate(user=self.user)

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.temp_media_root, ignore_errors=True)

    def test_patch_uploads_avatar_and_returns_user_url(self):
        avatar = SimpleUploadedFile('avatar.jpg', b'fake-image-content', content_type='image/jpeg')

        with patch(
            'django.core.files.storage.filesystem.FileSystemStorage.save',
            return_value='avatars/user_1/test-avatar.jpg',
        ):
            response = self.client.patch(
                '/api/auth/me/avatar/',
                {'avatar': avatar},
                format='multipart',
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(bool(self.user.profile.avatar))
        self.assertIn('/media/avatars/', response.data['user']['avatar'])

    def test_delete_removes_avatar(self):
        self.user.profile.avatar = 'avatars/user_1/test-avatar.jpg'
        self.user.profile.save(update_fields=['avatar'])

        with patch('django.core.files.storage.filesystem.FileSystemStorage.delete') as delete_mock:
            response = self.client.delete('/api/auth/me/avatar/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        delete_mock.assert_called_once()
        self.user.refresh_from_db()
        self.assertFalse(bool(self.user.profile.avatar))
        self.assertIsNone(response.data['user']['avatar'])


class ApiDocumentationTests(APITestCase):
    """Valida esquema OpenAPI y pagina HTML de documentacion."""

    def test_api_root_exposes_docs_links(self):
        response = self.client.get('/api/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('docs_url', response.data)
        self.assertIn('schema_url', response.data)

    def test_schema_endpoint_returns_openapi_document(self):
        response = self.client.get('/api/schema/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['openapi'], '3.0.3')
        self.assertIn('/api/auth/login/', response.data['paths'])
        self.assertIn('components', response.data)
        self.assertIn('securitySchemes', response.data['components'])

    def test_docs_endpoint_renders_html(self):
        response = self.client.get('/api/docs/', HTTP_ACCEPT='text/html')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(b'Documentacion operativa de GrocerySaver API', response.content)
        self.assertIn(b'/api/schema/', response.content)
