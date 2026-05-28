"""Главный модуль маршрутизации проекта.

Здесь подключаются все URL-маршруты: и встроенные (admin, auth),
и наши собственные из приложения core.
"""
from django.contrib import admin
from django.urls import path, include


urlpatterns = [
    # Административный интерфейс Django (по умолчанию доступен по /admin/).
    path("admin/", admin.site.urls),

    # Стандартные страницы аутентификации Django:
    # /accounts/login/, /accounts/logout/, /accounts/password_change/ и т. д.
    path("accounts/", include("django.contrib.auth.urls")),

    # Все маршруты нашего приложения core подключены к корню сайта.
    path("", include("core.urls")),
]
