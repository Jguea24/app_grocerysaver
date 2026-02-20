from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from .models import EmailVerificationToken, Product, Role, SocialAccount, UserProfile


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
        self.assertEqual(response.data['best_option']['store'], 'Toti')
        self.assertEqual(response.data['best_option']['price'], '1.05')
        self.assertEqual(response.data['most_expensive_option']['store'], 'Tia')
        self.assertEqual(response.data['most_expensive_option']['price'], '2.25')
        self.assertEqual(response.data['savings_vs_most_expensive'], '1.20')
