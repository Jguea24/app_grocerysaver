"""Servicios del dominio de precios."""

from .models import PriceHistory


def record_price_history(product_price, source='current_price_sync'):
    """Crea un snapshot historico cuando el precio vigente cambia."""
    latest = PriceHistory.objects.filter(product=product_price.product, store=product_price.store).order_by('-captured_at').first()
    if latest is not None and latest.price == product_price.price:
        return latest

    return PriceHistory.objects.create(
        product=product_price.product,
        store=product_price.store,
        price=product_price.price,
        source=source,
    )