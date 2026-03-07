"""Señales de dominio para codigos QR e invalidacion de cache."""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .cache_utils import invalidate_catalog_caches, invalidate_raffle_cache
from .models import Category, Offer, Product, ProductCode, ProductPrice, Raffle, Role, Store
from .services import ensure_product_qr_code


@receiver(post_save, sender=Product)
def create_product_qr_code(sender, instance, created, **kwargs):
    """Asigna un QR automatico a cada producto nuevo."""
    if kwargs.get('raw'):
        return
    if created:
        ensure_product_qr_code(instance)


@receiver(post_save, sender=Role)
@receiver(post_delete, sender=Role)
@receiver(post_save, sender=Store)
@receiver(post_delete, sender=Store)
@receiver(post_save, sender=Category)
@receiver(post_delete, sender=Category)
@receiver(post_save, sender=Product)
@receiver(post_delete, sender=Product)
@receiver(post_save, sender=ProductCode)
@receiver(post_delete, sender=ProductCode)
@receiver(post_save, sender=ProductPrice)
@receiver(post_delete, sender=ProductPrice)
@receiver(post_save, sender=Offer)
@receiver(post_delete, sender=Offer)
def invalidate_public_catalog(sender, **kwargs):
    """Invalida cache publico cuando cambia el catalogo visible."""
    if kwargs.get('raw'):
        return
    invalidate_catalog_caches()


@receiver(post_save, sender=Raffle)
@receiver(post_delete, sender=Raffle)
def invalidate_active_raffles(sender, **kwargs):
    """Invalida la cache de rifas cuando cambia una rifa."""
    if kwargs.get('raw'):
        return
    invalidate_raffle_cache()
