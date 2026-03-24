"""Tests del dominio de alertas."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from grocerysaver.models import Category, Product, Role, UserProfile
from inventory.models import InventoryItem

from .models import AlertStatus


class AlertEndpointTests(APITestCase):
    """Valida lectura y cambio de estado de alertas."""

    def setUp(self):
        self.role, _ = Role.objects.get_or_create(name='cliente')
        self.user = get_user_model().objects.create_user(
            username='alerts.user',
            email='alerts@example.com',
            password='TestPass123!@#',
            is_active=True,
        )
        UserProfile.objects.create(
            user=self.user,
            role=self.role,
            address='Centro',
            birth_date='1991-02-02',
        )
        self.client.force_authenticate(self.user)

        category, _ = Category.objects.get_or_create(name='Refrigerados')
        product = Product.objects.create(category=category, name='Yogurt', brand='GS')
        self.inventory_item = InventoryItem.objects.create(
            user=self.user,
            product=product,
            quantity=2,
            expires_at=timezone.localdate() + timedelta(days=1),
        )
        self.alert = self.inventory_item.alerts.get()

    def test_list_active_alerts(self):
        response = self.client.get('/api/alerts/?status=active')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['alerts']), 1)
        self.assertEqual(response.data['alerts'][0]['status'], AlertStatus.ACTIVE)

    def test_patch_alert_status(self):
        response = self.client.patch(
            f'/api/alerts/{self.alert.id}/',
            {'status': AlertStatus.DISMISSED},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['alert']['status'], AlertStatus.DISMISSED)
