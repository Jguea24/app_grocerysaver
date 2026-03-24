"""Configuracion de la app orders."""

from django.apps import AppConfig


class OrdersConfig(AppConfig):
    """Metadatos base para el dominio de ordenes."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'orders'
    verbose_name = 'Orders'
