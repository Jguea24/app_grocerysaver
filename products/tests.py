"""Tests del dominio de productos."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from grocerysaver.models import Category, Product, ProductCode, ProductCodeType, ProductPrice, Role, Store, UserProfile

from .models import ProductPurchase


class ProductRouterTests(APITestCase):
    """Valida catalogo, detalle y compras expuestos por router."""

    def setUp(self):
        self.category, _ = Category.objects.get_or_create(name='Lacteos Router')
        self.product = Product.objects.create(category=self.category, name='Queso Fresco', brand='GS Router')
        self.cheaper_product = Product.objects.create(category=self.category, name='Queso Ahorro', brand='GS Basic')
        self.store, _ = Store.objects.get_or_create(name='Santa Maria')
        self.other_store, _ = Store.objects.get_or_create(name='Aki')
        ProductPrice.objects.create(product=self.product, store=self.store, price='3.45')
        ProductPrice.objects.create(product=self.product, store=self.other_store, price='3.15')
        ProductPrice.objects.create(product=self.cheaper_product, store=self.store, price='2.70')
        ProductCode.objects.create(product=self.product, code='1234567890123', code_type=ProductCodeType.BARCODE)

        role, _ = Role.objects.get_or_create(name='cliente')
        self.user = get_user_model().objects.create_user(
            username='product.user',
            email='product@example.com',
            password='TestPass123!@#',
            is_active=True,
        )
        UserProfile.objects.create(
            user=self.user,
            role=role,
            address='Centro',
            birth_date='1992-02-02',
        )

    def test_categories_list_route_remains_available(self):
        response = self.client.get('/api/categories/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(any(category['id'] == self.category.id for category in response.data['categories']))

    def test_products_list_route_remains_available(self):
        response = self.client.get('/api/products/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(any(product['id'] == self.product.id for product in response.data['products']))

    def test_products_list_supports_barcode_filter(self):
        response = self.client.get('/api/products/?barcode=1234567890123')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['products']), 1)
        self.assertEqual(response.data['products'][0]['id'], self.product.id)

    def test_product_scan_route_remains_available(self):
        response = self.client.post('/api/products/scan/', {'code': '1234567890123'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['product']['id'], self.product.id)

    def test_product_detail_includes_estimated_price_and_alternatives(self):
        ProductPurchase.objects.create(
            user=self.user,
            product=self.product,
            store=self.store,
            quantity=2,
            unit_price='3.20',
            purchased_at=timezone.now() - timedelta(days=2),
        )
        self.client.force_authenticate(self.user)

        response = self.client.get(f'/api/products/{self.product.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['product']['id'], self.product.id)
        self.assertEqual(response.data['product']['estimated_price'], '3.30')
        self.assertEqual(response.data['purchase_summary']['purchases_count'], 1)
        self.assertEqual(len(response.data['cheaper_alternatives']), 1)
        self.assertEqual(response.data['cheaper_alternatives'][0]['id'], self.cheaper_product.id)

    def test_purchase_history_endpoints_allow_create_and_list(self):
        self.client.force_authenticate(self.user)

        create_response = self.client.post(
            '/api/products/purchases/',
            {
                'product_id': self.product.id,
                'store_id': self.store.id,
                'quantity': 3,
                'unit_price': '3.10',
            },
            format='json',
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_response.data['purchase']['quantity'], 3)

        list_response = self.client.get(f'/api/products/purchases/?product_id={self.product.id}')
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data['purchases']), 1)
        self.assertEqual(list_response.data['purchases'][0]['unit_price'], '3.10')
