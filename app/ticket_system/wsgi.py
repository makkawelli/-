"""WSGI-конфигурация для развёртывания на боевом сервере.

WSGI — стандартный интерфейс между Python-приложением и веб-сервером
(Gunicorn, uWSGI, mod_wsgi и т. п.). На разработке используется
встроенный сервер Django (`python manage.py runserver`), и этот файл
вызывается автоматически.
"""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ticket_system.settings")

application = get_wsgi_application()
