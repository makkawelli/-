"""Контроллеры приложения core."""
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render

from . import models


@login_required
def home(request):
    """Главная страница / дашборд.

    Защищено @login_required — неавторизованный пользователь будет
    автоматически переадресован на /accounts/login/ (LOGIN_URL в settings.py).

    Содержит общие счётчики по справочникам и заявкам, а также «мой блок»
    для текущего пользователя: количество заявок, где он исполнитель.
    """
    # Общие метрики системы.
    requests_qs = models.Request.objects.all()
    overall = {
        "requests_total":   requests_qs.count(),
        "requests_open":    requests_qs.filter(status__is_terminal=False).count(),
        "requests_closed":  requests_qs.filter(status__is_terminal=True).count(),
        "clients_total":    models.Client.objects.count(),
        "services_total":   models.Service.objects.filter(is_active=True).count(),
        "employees_total":  models.Employee.objects.filter(is_active=True).count(),
        "field_defs_total": models.FieldDefinition.objects.filter(is_active=True).count(),
    }

    # Распределение по статусам — пригодится для дашборда.
    status_distribution = (
        models.Status.objects
        .annotate(cnt=Count("requests"))
        .order_by("order_num")
    )

    # «Мои заявки» — где текущий пользователь является исполнителем.
    my_requests = (
        models.Request.objects
        .filter(assignee=request.user, status__is_terminal=False)
        .select_related("client", "service", "status", "priority")
        .order_by("-created_at")[:5]
    )

    context = {
        "page_title": "Главная",
        "overall": overall,
        "status_distribution": status_distribution,
        "my_requests": my_requests,
        "my_requests_total": models.Request.objects.filter(
            assignee=request.user, status__is_terminal=False
        ).count(),
    }
    return render(request, "core/home.html", context)
