from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import (
    Address,
    Category,
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


class AuthFlowTests(APITestCase):
    def setUp(self):
        self.cliente_role, _ = Role.objects.get_or_create(
            name='cliente',
            defaults={'description': 'Cliente de la aplicacion'},
        )
        self.admin_role, _ = Role.objects.get_or_create(
            name='admin',
            defaults={'description': 'Administrador de la aplicacion'},
        )

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

    def test_social_login_creates_user_and_account(self):
        response = self.client.post(
            '/api/auth/social-login/',
            {
                'provider': 'facebook',
                'provider_user_id': 'facebook-123',
                'email': 'social@example.com',
                'first_name': 'Social',
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
                provider='facebook',
                provider_user_id='facebook-123',
            ).exists()
        )

    def test_social_login_requires_provider_user_id(self):
        response = self.client.post(
            '/api/auth/social-login/',
            {
                'provider': 'facebook',
                'email': 'social@example.com',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('provider_user_id', response.data)


class CatalogComparisonTests(APITestCase):
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
    def setUp(self):
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
    def setUp(self):
        self.category = Category.objects.create(name='Lacteos')
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
    def setUp(self):
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


class WeatherEndpointTests(APITestCase):
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


class EcuadorGeoCatalogTests(APITestCase):
    def test_ecuador_geo_returns_country_and_provinces(self):
        response = self.client.get('/api/geo/ecuador/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['country'], 'Ecuador')
        self.assertEqual(len(response.data['provinces']), 24)

    def test_ecuador_provinces_summary(self):
        response = self.client.get('/api/geo/ecuador/provinces/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['country'], 'Ecuador')
        self.assertEqual(len(response.data['provinces']), 24)
        self.assertIn('cantons_count', response.data['provinces'][0])

    def test_ecuador_cantons_by_province_id(self):
        response = self.client.get('/api/geo/ecuador/cantons/?province_id=1')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['province']['name'], 'Azuay')
        self.assertGreaterEqual(len(response.data['cantons']), 1)

    def test_ecuador_cantons_requires_province(self):
        response = self.client.get('/api/geo/ecuador/cantons/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('province_id o province', response.data['detail'])
