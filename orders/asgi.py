"""Точка входа ASGI для проекта orders."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'orders.settings')

application = get_asgi_application()
