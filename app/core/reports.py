"""Расчётный слой отчётности.

Отделяет SQL-логику отчётов от views. Каждая функция возвращает «сырой»
результат (список словарей или queryset), который view либо рендерит
в HTML, либо отдаёт в CSV.

Все запросы — на стороне БД, через ORM-агрегаты, чтобы не тащить
тысячи объектов в Python-слой.
"""
from __future__ import annotations

import datetime as dt
from datetime import date, timedelta

from django.db.models import (
    Avg, Count, DurationField, ExpressionWrapper, F, Q,
)
from django.db.models.functions import TruncDay
from django.utils import timezone

from . import models


# =============================================================================
# Утилиты
# =============================================================================
def parse_date(s: str | None) -> date | None:
    """Безопасный парсер ISO-даты из GET-параметра. None при ошибке."""
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def default_period() -> tuple[date, date]:
    """Период по умолчанию: последние 30 дней включительно."""
    today = timezone.localdate()
    return today - timedelta(days=29), today


# =============================================================================
# Отчёт 1. Динамика по периоду — сколько создано / закрыто по дням.
# =============================================================================
def report_by_period(date_from: date, date_to: date) -> dict:
    """Агрегация заявок по датам в диапазоне [date_from, date_to].

    Возвращает:
        - rows: список {date, created, closed} — по одной записи на день;
        - totals: общие суммы;
        - chart: словарь со списками для Chart.js.
    """
    # Превращаем границы в datetime, чтобы фильтр по timestamp с TZ был корректным.
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(
        dt.datetime.combine(date_from, dt.time.min), tz,
    )
    end_excl = timezone.make_aware(
        dt.datetime.combine(date_to + timedelta(days=1), dt.time.min), tz,
    )

    # «Создано» — группировка по created_at.
    created_qs = (
        models.Request.objects
        .filter(created_at__gte=start, created_at__lt=end_excl)
        .annotate(d=TruncDay("created_at"))
        .values("d")
        .annotate(cnt=Count("id"))
    )
    created_map = {row["d"].date(): row["cnt"] for row in created_qs}

    # «Закрыто» — группировка по closed_at.
    closed_qs = (
        models.Request.objects
        .filter(closed_at__gte=start, closed_at__lt=end_excl)
        .annotate(d=TruncDay("closed_at"))
        .values("d")
        .annotate(cnt=Count("id"))
    )
    closed_map = {row["d"].date(): row["cnt"] for row in closed_qs}

    rows = []
    cur = date_from
    total_created = 0
    total_closed = 0
    while cur <= date_to:
        c = created_map.get(cur, 0)
        cl = closed_map.get(cur, 0)
        rows.append({"date": cur, "created": c, "closed": cl})
        total_created += c
        total_closed += cl
        cur += timedelta(days=1)

    return {
        "rows": rows,
        "totals": {"created": total_created, "closed": total_closed},
        "chart": {
            "labels":  [r["date"].strftime("%d.%m") for r in rows],
            "created": [r["created"] for r in rows],
            "closed":  [r["closed"] for r in rows],
        },
    }


# =============================================================================
# Отчёт 2. Загрузка исполнителей.
# =============================================================================
def report_executors() -> list[dict]:
    """Сводка по исполнителям: открытых, выполнено, среднее время, просрочка.

    Возвращает список словарей с полями: full_name, total, open, done,
    overdue, avg_hours.
    """
    now = timezone.now()
    qs = (
        models.Employee.objects
        .filter(is_active=True, role__code__in=["executor", "manager"])
        .annotate(
            total=Count("assigned_requests"),
            open=Count(
                "assigned_requests",
                filter=Q(assigned_requests__status__is_terminal=False),
            ),
            done=Count(
                "assigned_requests",
                filter=Q(assigned_requests__status__code="done"),
            ),
            overdue=Count(
                "assigned_requests",
                filter=Q(
                    assigned_requests__due_date__lt=now,
                    assigned_requests__status__is_terminal=False,
                ),
            ),
            avg_seconds=Avg(
                ExpressionWrapper(
                    F("assigned_requests__closed_at") - F("assigned_requests__created_at"),
                    output_field=DurationField(),
                ),
                filter=Q(assigned_requests__status__is_terminal=True),
            ),
        )
        .order_by("-total")
    )

    result = []
    for e in qs:
        avg_hours = None
        if e.avg_seconds is not None:
            avg_hours = round(e.avg_seconds.total_seconds() / 3600.0, 1)
        result.append({
            "id": e.id,
            "full_name": e.full_name or e.username,
            "username": e.username,
            "role": e.role.name if e.role_id else "",
            "total": e.total,
            "open": e.open,
            "done": e.done,
            "overdue": e.overdue,
            "avg_hours": avg_hours,
        })
    return result


# =============================================================================
# Отчёт 3. SLA — соблюдение сроков по приоритетам.
# =============================================================================
def report_sla() -> dict:
    """Статистика соблюдения SLA по приоритетам.

    Считаем по закрытым заявкам:
        - в срок:        closed_at <= due_date;
        - с просрочкой:  closed_at > due_date.
    Открытые отдельно — сколько уже просрочено (now > due_date).
    """
    now = timezone.now()

    rows = []
    grand_in_time = grand_overdue = grand_open_overdue = grand_total_closed = 0

    for p in models.Priority.objects.order_by("sla_hours"):
        closed = models.Request.objects.filter(priority=p, status__is_terminal=True)
        in_time = closed.filter(closed_at__lte=F("due_date")).count()
        overdue = closed.filter(closed_at__gt=F("due_date")).count()
        total_closed = in_time + overdue

        open_overdue = (
            models.Request.objects
            .filter(priority=p, status__is_terminal=False, due_date__lt=now)
            .count()
        )

        sla_pct = (in_time * 100 / total_closed) if total_closed else None

        rows.append({
            "priority": p.name,
            "priority_code": p.code,
            "sla_hours": p.sla_hours,
            "in_time": in_time,
            "overdue": overdue,
            "total_closed": total_closed,
            "open_overdue": open_overdue,
            "sla_pct": round(sla_pct, 1) if sla_pct is not None else None,
        })
        grand_in_time += in_time
        grand_overdue += overdue
        grand_open_overdue += open_overdue
        grand_total_closed += total_closed

    grand_pct = (grand_in_time * 100 / grand_total_closed) if grand_total_closed else None

    return {
        "rows": rows,
        "totals": {
            "in_time": grand_in_time,
            "overdue": grand_overdue,
            "open_overdue": grand_open_overdue,
            "total_closed": grand_total_closed,
            "sla_pct": round(grand_pct, 1) if grand_pct is not None else None,
        },
    }


# =============================================================================
# Сводные «живые» метрики для индекса.
# =============================================================================
def live_dashboard_metrics() -> dict:
    """Метрики реального времени для индекса отчётов / дашборда менеджера."""
    now = timezone.now()

    open_qs = models.Request.objects.filter(status__is_terminal=False)
    by_status = (
        open_qs.values("status__id", "status__name", "status__code")
        .annotate(cnt=Count("id"))
        .order_by("status__order_num")
    )
    by_priority = (
        open_qs.values("priority__id", "priority__name", "priority__code")
        .annotate(cnt=Count("id"))
        .order_by("priority__sla_hours")
    )

    return {
        "open_total":   open_qs.count(),
        "overdue":      open_qs.filter(due_date__lt=now).count(),
        "unassigned":   open_qs.filter(assignee__isnull=True).count(),
        "by_status":    list(by_status),
        "by_priority":  list(by_priority),
    }
