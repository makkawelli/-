"""URL-маршруты приложения core.

Подключаются в ticket_system/urls.py через include('core.urls').
"""
from django.urls import path

from . import views


# app_name позволяет ссылаться на маршруты как "core:home" в шаблонах.
app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
]
