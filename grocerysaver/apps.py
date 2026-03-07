"""Configuracion de la app GrocerySaver."""

from django.apps import AppConfig


class GrocerysaverConfig(AppConfig):
    """Declara metadatos de la app y conecta sus señales al iniciar."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'grocerysaver'

    def ready(self):
        """Importa el modulo de señales para registrar receivers."""
        from . import signals  # noqa: F401
