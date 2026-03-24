"""Configuracion de la app products."""

from django.apps import AppConfig


class ProductsConfig(AppConfig):
    """Metadatos base para el dominio de productos."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'products'
    verbose_name = 'Products'