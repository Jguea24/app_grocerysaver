from django.apps import AppConfig


class GrocerysaverConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'grocerysaver'

    def ready(self):
        from . import signals  # noqa: F401
