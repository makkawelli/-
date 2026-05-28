"""ASGI-конфигурация (для асинхронных серверов вроде Daphne, Uvicorn).

В нашем прототипе не используется, но Django создаёт этот файл по умолчанию,
и оставляем его для совместимости.
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ticket_system.settings")

application = get_asgi_application()
