"""Modelos del dominio de precios."""

from django.db import models

from grocerysaver.models import Offer, ProductPrice, Store


class PriceHistory(models.Model):
    """Snapshot historico del precio de un producto en una tienda."""

    product = models.ForeignKey(
        'grocerysaver.Product',
        on_delete=models.CASCADE,
        related_name='price_history',
    )
    store = models.ForeignKey(
        'grocerysaver.Store',
        on_delete=models.CASCADE,
        related_name='price_history',
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    captured_at = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=40, default='current_price_sync')

    class Meta:
        ordering = ['-captured_at', 'price']
        indexes = [
            models.Index(fields=['product', 'store', '-captured_at']),
            models.Index(fields=['store', '-captured_at']),
        ]

    def __str__(self):
        return f'PriceHistory(product={self.product_id}, store={self.store_id}, price={self.price})'


__all__ = ['Offer', 'PriceHistory', 'ProductPrice', 'Store']