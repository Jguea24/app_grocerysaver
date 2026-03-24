"""Tests del dominio de precios."""

from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from grocerysaver.models import Category, Product, ProductPrice, Store

from .models import PriceHistory


class PriceHistoryTests(APITestCase):
    """Valida snapshots historicos y endpoints de consulta."""

    def setUp(self):
        self.category, _ = Category.objects.get_or_create(name='Bebidas')
        self.product = Product.objects.create(category=self.category, name='Leche Entera', brand='GS Prices')
        self.store_a, _ = Store.objects.get_or_create(name='Megamaxi')
        self.store_b, _ = Store.objects.get_or_create(name='Tia')
        self.current_price = ProductPrice.objects.create(product=self.product, store=self.store_a, price='1.95')
        self.other_price = ProductPrice.objects.create(product=self.product, store=self.store_b, price='2.10')

    def test_creating_product_price_generates_history_snapshot(self):
        snapshots = PriceHistory.objects.filter(product=self.product, store=self.store_a)

        self.assertEqual(snapshots.count(), 1)
        self.assertEqual(snapshots.first().price, Decimal('1.95'))

    def test_updating_product_price_with_new_value_creates_new_snapshot(self):
        self.current_price.price = Decimal('1.79')
        self.current_price.save(update_fields=['price', 'updated_at'])

        snapshots = PriceHistory.objects.filter(product=self.product, store=self.store_a).order_by('-captured_at', '-id')

        self.assertEqual(snapshots.count(), 2)
        self.assertEqual(snapshots.first().price, Decimal('1.79'))

    def test_history_endpoint_returns_product_history(self):
        response = self.client.get(f'/api/prices/history/?product_id={self.product.id}&limit=10')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['product']['id'], self.product.id)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(len(response.data['history']), 2)
        self.assertEqual(len(response.data['latest_by_store']), 2)

    def test_compare_prices_includes_price_history(self):
        response = self.client.get(f'/api/compare-prices/?product_id={self.product.id}')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['product']['id'], self.product.id)
        self.assertIn('price_history', response.data)
        self.assertEqual(len(response.data['price_history']), 2)
