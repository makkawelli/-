"""Конфигурация Django-приложения core.

Каждое приложение Django имеет AppConfig, в котором можно задать
человекочитаемое имя и подключить сигналы при старте.
"""
from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Учёт заявок"
