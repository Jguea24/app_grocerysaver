"""Senales para mantener alertas sincronizadas con el inventario."""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from inventory.models import InventoryItem

from .models import Alert, AlertStatus, AlertType
from .services import sync_expiry_alert_for_item


@receiver(post_save, sender=InventoryItem)
def sync_inventory_item_alert(sender, instance, **kwargs):
    """Sincroniza la alerta de expiracion al guardar un item de inventario."""
    if kwargs.get('raw'):
        return
    sync_expiry_alert_for_item(instance)


@receiver(post_delete, sender=InventoryItem)
def resolve_deleted_inventory_alerts(sender, instance, **kwargs):
    """Marca como resueltas las alertas activas cuando el item se elimina."""
    if kwargs.get('raw'):
        return
    Alert.objects.filter(
        inventory_item=instance,
        type=AlertType.EXPIRY,
        status=AlertStatus.ACTIVE,
    ).update(status=AlertStatus.RESOLVED, resolved_at=timezone.now())