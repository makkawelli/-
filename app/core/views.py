"""Контроллеры приложения core."""
from django.shortcuts import render

from . import models


def home(request):
    """Главная страница приложения.

    Показывает приветствие и базовую статистику по справочникам и заявкам,
    чтобы наглядно видеть, что БД подключена и наполнена.
    """
    context = {
        "page_title": "Главная",
        "stats": {
            "requests_total":   models.Request.objects.count(),
            "requests_open":    models.Request.objects.filter(status__is_terminal=False).count(),
            "clients_total":    models.Client.objects.count(),
            "services_total":   models.Service.objects.filter(is_active=True).count(),
            "employees_total":  models.Employee.objects.filter(is_active=True).count(),
            "field_defs_total": models.FieldDefinition.objects.filter(is_active=True).count(),
        },
    }
    return render(request, "core/home.html", context)
