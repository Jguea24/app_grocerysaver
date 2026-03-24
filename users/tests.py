"""Tests del dominio de usuarios."""

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from grocerysaver.models import Role, UserProfile


class SavingsPreferenceTests(APITestCase):
    """Valida preferencias de ahorro y su exposicion en /me/."""

    def setUp(self):
        role, _ = Role.objects.get_or_create(name='cliente')
        self.user = get_user_model().objects.create_user(
            username='savings.user',
            email='savings@example.com',
            password='TestPass123!@#',
            is_active=True,
        )
        UserProfile.objects.create(
            user=self.user,
            role=role,
            address='Centro',
            birth_date='1993-03-03',
        )
        self.client.force_authenticate(self.user)

    def test_get_savings_preferences_creates_default_record(self):
        response = self.client.get('/api/profile/savings-preferences/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['savings_preferences']['savings_target_percentage'], 10)
        self.assertTrue(response.data['savings_preferences']['prefer_discounted_products'])

    def test_patch_savings_preferences_updates_me_payload(self):
        patch_response = self.client.patch(
            '/api/profile/savings-preferences/',
            {
                'preferred_budget': '120.00',
                'savings_target_percentage': 18,
                'allow_generic_brands': False,
            },
            format='json',
        )

        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_response.data['savings_preferences']['preferred_budget'], '120.00')
        self.assertEqual(patch_response.data['user']['savings_preferences']['savings_target_percentage'], 18)
        self.assertFalse(patch_response.data['user']['savings_preferences']['allow_generic_brands'])

        me_response = self.client.get('/api/auth/me/')
        self.assertEqual(me_response.status_code, status.HTTP_200_OK)
        self.assertEqual(me_response.data['user']['savings_preferences']['preferred_budget'], '120.00')
