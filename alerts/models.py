"""Modelos del dominio de alertas."""

from django.conf import settings
from django.db import models
from django.db.models import Q


class AlertType(models.TextChoices):
    """Tipos de alertas soportadas por el sistema."""

    EXPIRY = 'expiry', 'Expiry'


class AlertStatus(models.TextChoices):
    """Estados de ciclo de vida de una alerta."""

    ACTIVE = 'active', 'Active'
    RESOLVED = 'resolved', 'Resolved'
    DISMISSED = 'dismissed', 'Dismissed'


class Alert(models.Model):
    """Alerta generada para el usuario a partir de reglas de negocio."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='alerts',
    )
    inventory_item = models.ForeignKey(
        'inventory.InventoryItem',
        on_delete=models.CASCADE,
        related_name='alerts',
    )
    product = models.ForeignKey(
        'grocerysaver.Product',
        on_delete=models.CASCADE,
        related_name='alerts',
    )
    type = models.CharField(max_length=20, choices=AlertType.choices, default=AlertType.EXPIRY)
    status = models.CharField(max_length=20, choices=AlertStatus.choices, default=AlertStatus.ACTIVE)
    days_remaining = models.IntegerField()
    message = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['days_remaining', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['inventory_item', 'type'],
                condition=Q(status=AlertStatus.ACTIVE),
                name='uniq_active_alert_per_inventory_item_and_type',
            ),
        ]
        indexes = [
            models.Index(fields=['user', 'status', 'days_remaining']),
        ]

    def __str__(self):
        return f'Alert(user={self.user_id}, inventory_item={self.inventory_item_id}, type={self.type})'