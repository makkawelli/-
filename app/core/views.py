"""Контроллеры приложения core (Django views)."""
from __future__ import annotations

import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import forms, models, permissions, reports, services


# =============================================================================
# Главная (дашборд)
# =============================================================================
@login_required
def home(request):
    """Главная страница / дашборд.

    Защищено @login_required — неавторизованный будет переадресован на login.
    Содержит общие счётчики, распределение по статусам и блок «мои заявки».
    """
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

    status_distribution = (
        models.Status.objects
        .annotate(cnt=Count("requests"))
        .order_by("order_num")
    )

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


# =============================================================================
# Список заявок
# =============================================================================
@login_required
def request_list(request):
    """Страница со списком заявок: фильтры, поиск, пагинация."""
    qs = permissions.visible_requests_qs(request.user).order_by("-created_at")

    # Применяем фильтры из GET.
    filter_form = forms.RequestFilterForm(request.GET or None)
    if filter_form.is_valid():
        cd = filter_form.cleaned_data
        if cd.get("q"):
            term = cd["q"]
            qs = qs.filter(
                Q(number__icontains=term)
                | Q(title__icontains=term)
                | Q(description__icontains=term)
                | Q(client__name__icontains=term)
            )
        if cd.get("status"):
            qs = qs.filter(status=cd["status"])
        if cd.get("priority"):
            qs = qs.filter(priority=cd["priority"])
        if cd.get("assignee"):
            qs = qs.filter(assignee=cd["assignee"])
        if cd.get("only_open"):
            qs = qs.filter(status__is_terminal=False)

    # Пагинация.
    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page") or 1
    page_obj = paginator.get_page(page_number)

    context = {
        "page_title": "Заявки",
        "filter_form": filter_form,
        "page_obj": page_obj,
        "total_count": paginator.count,
        "can_create": permissions.can_create_request(request.user),
    }
    return render(request, "core/request_list.html", context)


# =============================================================================
# Карточка заявки
# =============================================================================
@login_required
def request_detail(request, number: str):
    """Карточка заявки: метаданные, кастомные поля, история, комментарии."""
    req = get_object_or_404(
        models.Request.objects.select_related(
            "client", "service", "status", "priority", "assignee", "created_by"
        ),
        number=number,
    )
    if not permissions.can_view_request(request.user, req):
        return HttpResponseForbidden("Доступ к этой заявке закрыт.")

    # Кастомные поля для отображения: подмешиваем label из FieldDefinition.
    custom_fields_view = []
    fd_index = {fd.code: fd for fd in models.FieldDefinition.objects.filter(is_active=True)}
    for code, value in (req.custom_fields or {}).items():
        fd = fd_index.get(code)
        if not fd:
            # Поле было удалено — показываем «как есть».
            custom_fields_view.append({"label": code, "value": value, "type": "text"})
            continue
        # Для checkbox показываем «Да/Нет».
        if fd.field_type == "checkbox":
            display = "Да" if value else "Нет"
        else:
            display = value
        custom_fields_view.append({
            "label": fd.label,
            "value": display,
            "type": fd.field_type,
        })

    # История статусов и комментарии — берём в одном запросе.
    history = (
        req.status_history
        .select_related("status_from", "status_to", "changed_by")
        .order_by("changed_at")
    )
    comments = (
        req.comments.select_related("author").order_by("created_at")
    )

    # Доступные переходы статусов и форма комментариев.
    transitions = []
    for code in permissions.allowed_transitions_for(req):
        if permissions.can_transition(request.user, req, code):
            target = models.Status.objects.get(code=code)
            transitions.append(target)

    context = {
        "page_title": f"Заявка {req.number}",
        "req": req,
        "custom_fields_view": custom_fields_view,
        "history": history,
        "comments": comments,
        "transitions": transitions,
        "comment_form": forms.CommentForm(),
        "can_edit": permissions.can_edit_request(request.user, req),
    }
    return render(request, "core/request_detail.html", context)


# =============================================================================
# Создание заявки
# =============================================================================
@login_required
def request_create(request):
    """Форма создания новой заявки."""
    if not permissions.can_create_request(request.user):
        return HttpResponseForbidden("У вас нет прав создавать заявки.")

    if request.method == "POST":
        form = forms.RequestForm(request.POST)
        if form.is_valid():
            req = services.create_request(
                client=form.cleaned_data["client"],
                service=form.cleaned_data["service"],
                priority=form.cleaned_data["priority"],
                title=form.cleaned_data["title"],
                description=form.cleaned_data["description"],
                created_by=request.user,
                assignee=form.cleaned_data.get("assignee"),
                custom_fields=form.get_custom_fields_payload(),
            )
            messages.success(request, f"Заявка {req.number} создана.")
            return redirect("core:request_detail", number=req.number)
    else:
        form = forms.RequestForm()

    context = {
        "page_title": "Новая заявка",
        "form": form,
        "is_create": True,
    }
    return render(request, "core/request_form.html", context)


# =============================================================================
# Редактирование заявки
# =============================================================================
@login_required
def request_edit(request, number: str):
    """Форма редактирования заявки. Доступна оператору/менеджеру/админу."""
    req = get_object_or_404(models.Request, number=number)
    if not permissions.can_edit_request(request.user, req):
        return HttpResponseForbidden("У вас нет прав редактировать эту заявку.")

    if request.method == "POST":
        form = forms.RequestForm(request.POST, instance=req)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.custom_fields = form.get_custom_fields_payload()
            obj.save()

            models.AuditLog.objects.create(
                actor=request.user,
                action="update",
                entity_type="request",
                entity_id=obj.id,
                payload={"number": obj.number},
            )
            messages.success(request, "Заявка сохранена.")
            return redirect("core:request_detail", number=obj.number)
    else:
        form = forms.RequestForm(instance=req)

    context = {
        "page_title": f"Редактирование {req.number}",
        "form": form,
        "req": req,
        "is_create": False,
    }
    return render(request, "core/request_form.html", context)


# =============================================================================
# Смена статуса
# =============================================================================
@login_required
@require_POST
def request_transition(request, number: str, to_status: str):
    """Перевод заявки в новый статус. Только POST."""
    req = get_object_or_404(models.Request, number=number)

    if not permissions.can_transition(request.user, req, to_status):
        return HttpResponseForbidden("Недопустимый переход статуса.")

    comment = (request.POST.get("comment") or "").strip()
    services.transition_request(
        request_obj=req,
        to_status_code=to_status,
        changed_by=request.user,
        comment=comment,
    )
    messages.success(request, f"Статус заявки изменён на «{req.status.name}».")
    return redirect("core:request_detail", number=req.number)


# =============================================================================
# Добавление комментария
# =============================================================================
@login_required
@require_POST
def request_add_comment(request, number: str):
    """Добавить комментарий к заявке. Только POST."""
    req = get_object_or_404(models.Request, number=number)

    if not permissions.can_comment_request(request.user, req):
        return HttpResponseForbidden("Доступ к заявке закрыт.")

    form = forms.CommentForm(request.POST)
    if form.is_valid():
        services.add_comment(
            request_obj=req,
            author=request.user,
            text=form.cleaned_data["text"],
            is_internal=form.cleaned_data.get("is_internal", False),
        )
        messages.success(request, "Комментарий добавлен.")
    else:
        messages.error(request, "Не удалось добавить комментарий: текст обязателен.")

    return redirect(reverse("core:request_detail", args=[req.number]) + "#comments")



# =============================================================================
# ОТЧЁТЫ (только для менеджера/админа)
# =============================================================================
def _require_reports_access(user):
    """Возвращает HttpResponseForbidden, если у пользователя нет прав на отчёты."""
    if not permissions.can_view_reports(user):
        return HttpResponseForbidden(
            "Раздел отчётов доступен только менеджеру и администратору."
        )
    return None


@login_required
def reports_index(request):
    """Главная страница раздела отчётов: «живые» метрики + ссылки на отчёты."""
    forbidden = _require_reports_access(request.user)
    if forbidden:
        return forbidden

    context = {
        "page_title": "Отчёты",
        "metrics": reports.live_dashboard_metrics(),
    }
    return render(request, "core/reports/index.html", context)


# ----- Отчёт 1: динамика по периоду -----------------------------------------
def _read_period_from_request(request):
    """Извлекает диапазон дат из GET (date_from, date_to). Сбрасывает на default."""
    df = reports.parse_date(request.GET.get("date_from"))
    dt_ = reports.parse_date(request.GET.get("date_to"))
    default_from, default_to = reports.default_period()
    return df or default_from, dt_ or default_to


@login_required
def report_period(request):
    forbidden = _require_reports_access(request.user)
    if forbidden:
        return forbidden

    date_from, date_to = _read_period_from_request(request)
    data = reports.report_by_period(date_from, date_to)
    context = {
        "page_title": "Отчёт: динамика по периоду",
        "date_from": date_from,
        "date_to": date_to,
        **data,
    }
    return render(request, "core/reports/by_period.html", context)


@login_required
def report_period_csv(request):
    forbidden = _require_reports_access(request.user)
    if forbidden:
        return forbidden

    date_from, date_to = _read_period_from_request(request)
    data = reports.report_by_period(date_from, date_to)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    # \ufeff — BOM, чтобы Excel корректно открывал кириллицу.
    response.write("\ufeff")
    response["Content-Disposition"] = (
        f'attachment; filename="report_period_{date_from}_{date_to}.csv"'
    )
    writer = csv.writer(response, delimiter=";")
    writer.writerow(["Дата", "Создано", "Закрыто"])
    for row in data["rows"]:
        writer.writerow([row["date"].strftime("%d.%m.%Y"), row["created"], row["closed"]])
    writer.writerow([])
    writer.writerow(["Итого", data["totals"]["created"], data["totals"]["closed"]])
    return response


# ----- Отчёт 2: загрузка исполнителей ---------------------------------------
@login_required
def report_executors_view(request):
    forbidden = _require_reports_access(request.user)
    if forbidden:
        return forbidden

    rows = reports.report_executors()
    context = {
        "page_title": "Отчёт: загрузка исполнителей",
        "rows": rows,
    }
    return render(request, "core/reports/executors.html", context)


@login_required
def report_executors_csv(request):
    forbidden = _require_reports_access(request.user)
    if forbidden:
        return forbidden

    rows = reports.report_executors()
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response.write("\ufeff")
    response["Content-Disposition"] = 'attachment; filename="report_executors.csv"'
    writer = csv.writer(response, delimiter=";")
    writer.writerow(["ФИО", "Логин", "Роль", "Всего", "Открытых", "Выполнено",
                     "Просрочено", "Среднее время решения, ч"])
    for r in rows:
        writer.writerow([
            r["full_name"], r["username"], r["role"],
            r["total"], r["open"], r["done"], r["overdue"],
            "" if r["avg_hours"] is None else r["avg_hours"],
        ])
    return response


# ----- Отчёт 3: SLA ---------------------------------------------------------
@login_required
def report_sla_view(request):
    forbidden = _require_reports_access(request.user)
    if forbidden:
        return forbidden

    data = reports.report_sla()
    context = {
        "page_title": "Отчёт: соблюдение SLA",
        **data,
    }
    return render(request, "core/reports/sla.html", context)


@login_required
def report_sla_csv(request):
    forbidden = _require_reports_access(request.user)
    if forbidden:
        return forbidden

    data = reports.report_sla()
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response.write("\ufeff")
    response["Content-Disposition"] = 'attachment; filename="report_sla.csv"'
    writer = csv.writer(response, delimiter=";")
    writer.writerow(["Приоритет", "SLA, ч", "Закрыто всего", "В срок",
                     "Просрочено", "Соблюдение, %", "Открытых просрочено"])
    for r in data["rows"]:
        writer.writerow([
            r["priority"], r["sla_hours"], r["total_closed"],
            r["in_time"], r["overdue"],
            "" if r["sla_pct"] is None else r["sla_pct"],
            r["open_overdue"],
        ])
    t = data["totals"]
    writer.writerow([])
    writer.writerow(["Итого", "", t["total_closed"], t["in_time"], t["overdue"],
                     "" if t["sla_pct"] is None else t["sla_pct"], t["open_overdue"]])
    return response
