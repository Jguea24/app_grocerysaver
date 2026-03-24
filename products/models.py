"""Modelos del dominio de productos."""

from django.conf import settings
from django.db import models

from grocerysaver.models import Category, Product, ProductCode, ProductCodeType, Store


class ProductPurchase(models.Model):
    """Historial de compras realizadas por el usuario para un producto."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='product_purchases',
    )
    product = models.ForeignKey(
        'grocerysaver.Product',
        on_delete=models.CASCADE,
        related_name='purchase_history',
    )
    store = models.ForeignKey(
        'grocerysaver.Store',
        on_delete=models.SET_NULL,
        related_name='product_purchases',
        null=True,
        blank=True,
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    purchased_at = models.DateTimeField()
    notes = models.CharField(max_length=255, blank=True)
    source = models.CharField(max_length=40, default='manual')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-purchased_at', '-id']
        indexes = [
            models.Index(fields=['user', 'product', '-purchased_at']),
            models.Index(fields=['product', '-purchased_at']),
        ]

    def __str__(self):
        return f'ProductPurchase(user={self.user_id}, product={self.product_id}, quantity={self.quantity})'


__all__ = ['Category', 'Product', 'ProductCode', 'ProductCodeType', 'ProductPurchase', 'Store']
