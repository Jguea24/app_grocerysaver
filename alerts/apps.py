"""Configuracion de la app alerts."""

from django.apps import AppConfig


class AlertsConfig(AppConfig):
    """Metadatos base para el dominio de alertas."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'alerts'
    verbose_name = 'Alerts'

    def ready(self):
        from . import signals  # noqa: F401