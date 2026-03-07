#!/usr/bin/env python
"""Punto de entrada para comandos administrativos del proyecto Django."""
import os
import sys
import threading
import webbrowser


def main():
    """Configura Django y delega la ejecucion al command runner oficial."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api_grocerysaver.settings')
    if 'runserver' in sys.argv and os.environ.get('RUN_MAIN') == 'true':
        # Abre el admin local automaticamente durante desarrollo.
        admin_url = 'http://127.0.0.1:8000/admin/login/?next=/admin/'
        threading.Timer(1.0, lambda: webbrowser.open(admin_url)).start()
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
