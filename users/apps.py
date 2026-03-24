"""Configuracion de la app users."""

from django.apps import AppConfig


class UsersConfig(AppConfig):
    """Metadatos base para el dominio de usuarios."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'
    verbose_name = 'Users'