"""Configuracion de la app prices."""

from django.apps import AppConfig


class PricesConfig(AppConfig):
    """Metadatos base para el dominio de precios."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'prices'
    verbose_name = 'Prices'

    def ready(self):
        from . import signals  # noqa: F401