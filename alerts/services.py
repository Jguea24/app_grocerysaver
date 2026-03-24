"""Servicios de negocio para el dominio de alertas."""

from django.conf import settings
from django.utils import timezone

from .models import Alert, AlertStatus, AlertType


DEFAULT_EXPIRY_ALERT_DAYS = getattr(settings, 'INVENTORY_EXPIRY_ALERT_DAYS', 3)


def build_expiry_message(inventory_item, days_remaining):
    """Genera un mensaje legible segun la distancia a la fecha de caducidad."""
    product_name = inventory_item.product.name
    if days_remaining < 0:
        return f'{product_name} ya caduco hace {abs(days_remaining)} dia(s).'
    if days_remaining == 0:
        return f'{product_name} caduca hoy.'
    return f'{product_name} caduca en {days_remaining} dia(s).'


def sync_expiry_alert_for_item(inventory_item, threshold_days=DEFAULT_EXPIRY_ALERT_DAYS):
    """Crea, actualiza o resuelve la alerta de caducidad de un item de inventario."""
    active_alert = Alert.objects.filter(
        inventory_item=inventory_item,
        type=AlertType.EXPIRY,
        status=AlertStatus.ACTIVE,
    ).first()

    if inventory_item.expires_at is None:
        if active_alert is not None:
            active_alert.status = AlertStatus.RESOLVED
            active_alert.resolved_at = timezone.now()
            active_alert.save(update_fields=['status', 'resolved_at', 'updated_at'])
        return None

    days_remaining = (inventory_item.expires_at - timezone.localdate()).days
    should_alert = days_remaining <= threshold_days

    if not should_alert:
        if active_alert is not None:
            active_alert.status = AlertStatus.RESOLVED
            active_alert.resolved_at = timezone.now()
            active_alert.save(update_fields=['status', 'resolved_at', 'updated_at'])
        return None

    message = build_expiry_message(inventory_item, days_remaining)
    if active_alert is None:
        return Alert.objects.create(
            user=inventory_item.user,
            inventory_item=inventory_item,
            product=inventory_item.product,
            type=AlertType.EXPIRY,
            status=AlertStatus.ACTIVE,
            days_remaining=days_remaining,
            message=message,
        )

    active_alert.product = inventory_item.product
    active_alert.days_remaining = days_remaining
    active_alert.message = message
    active_alert.resolved_at = None
    active_alert.save(update_fields=['product', 'days_remaining', 'message', 'resolved_at', 'updated_at'])
    return active_alert


def sync_all_expiry_alerts(threshold_days=DEFAULT_EXPIRY_ALERT_DAYS):
    """Sincroniza alertas de caducidad para todos los items del inventario."""
    from inventory.models import InventoryItem

    synced = 0
    for inventory_item in InventoryItem.objects.select_related('product', 'user'):
        sync_expiry_alert_for_item(inventory_item, threshold_days=threshold_days)
        synced += 1
    return synced