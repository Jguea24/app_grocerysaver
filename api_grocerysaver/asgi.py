"""Configuracion ASGI para despliegues asincronos del proyecto."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api_grocerysaver.settings')

application = get_asgi_application()
