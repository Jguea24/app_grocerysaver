"""Servicios auxiliares para poblar inventario demo en desarrollo."""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import InventoryItem


DEMO_EXPIRING_INVENTORY_BLUEPRINT = [
    {'product_name': 'Leche Entera 1L', 'quantity': 1, 'days_until_expiry': 0},
    {'product_name': 'Manzana Roja', 'quantity': 4, 'days_until_expiry': 1},
    {'product_name': 'Filete de Pescado 1kg', 'quantity': 1, 'days_until_expiry': 1},
    {'product_name': 'Tomate', 'quantity': 3, 'days_until_expiry': 2},
    {'product_name': 'Pechuga de Pollo 1kg', 'quantity': 2, 'days_until_expiry': 3},
]


def seed_demo_expiring_inventory_for_user(user):
    """Crea inventario demo con caducidad cercana para un usuario nuevo."""
    if not getattr(settings, 'AUTO_SEED_EXPIRING_INVENTORY', False):
        return []

    if user is None or getattr(user, 'is_staff', False):
        return []

    if InventoryItem.objects.filter(user=user).exists():
        return []

    from grocerysaver.models import Product

    seeded_items = []
    used_product_ids = set()
    today = timezone.localdate()

    for spec in DEMO_EXPIRING_INVENTORY_BLUEPRINT:
        product = (
            Product.objects.filter(name__iexact=spec['product_name'])
            .exclude(id__in=used_product_ids)
            .first()
        )
        if product is None:
            product = Product.objects.exclude(id__in=used_product_ids).order_by('id').first()
        if product is None:
            break

        used_product_ids.add(product.id)
        item, _ = InventoryItem.objects.update_or_create(
            user=user,
            product=product,
            expires_at=today + timedelta(days=spec['days_until_expiry']),
            defaults={'quantity': spec['quantity']},
        )
        seeded_items.append(item)

    return seeded_items
