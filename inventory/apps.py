"""Configuracion de la app inventory."""

from django.apps import AppConfig


class InventoryConfig(AppConfig):
    """Metadatos base para el dominio de inventario."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'inventory'
    verbose_name = 'Inventory'