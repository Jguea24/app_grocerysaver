"""Senales para mantener el historico de precios sincronizado."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from grocerysaver.models import ProductPrice

from .services import record_price_history


@receiver(post_save, sender=ProductPrice)
def create_price_history_snapshot(sender, instance, **kwargs):
    """Genera un snapshot historico cada vez que cambia el precio actual."""
    if kwargs.get('raw'):
        return
    record_price_history(instance)