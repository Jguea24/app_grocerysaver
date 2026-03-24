"""Modelos reales del dominio de inventario."""

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from grocerysaver.models import Cart, CartItem


class InventoryItem(models.Model):
    """Producto almacenado por un usuario dentro del inventario del hogar."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='inventory_items',
    )
    product = models.ForeignKey(
        'grocerysaver.Product',
        on_delete=models.CASCADE,
        related_name='inventory_items',
    )
    quantity = models.PositiveIntegerField(default=1)
    expires_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['expires_at', '-updated_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'product', 'expires_at'],
                name='uniq_inventory_item_user_product_expiry',
            ),
            models.CheckConstraint(condition=Q(quantity__gte=1), name='inventory_item_quantity_gte_1'),
        ]
        indexes = [
            models.Index(fields=['user', 'expires_at']),
            models.Index(fields=['product', 'expires_at']),
        ]

    @property
    def days_until_expiry(self):
        """Retorna dias restantes hasta la caducidad o None si no aplica."""
        if self.expires_at is None:
            return None
        return (self.expires_at - timezone.localdate()).days

    @property
    def is_expired(self):
        """Indica si el item ya caduco."""
        days = self.days_until_expiry
        return days is not None and days < 0

    def __str__(self):
        return f'InventoryItem(user={self.user_id}, product={self.product_id}, quantity={self.quantity})'


__all__ = ['Cart', 'CartItem', 'InventoryItem']