"""Тесты отчётов (расчётный слой).

Покрытие:
- parse_date / default_period — утилиты;
- report_by_period — по дням считает created/closed;
- report_executors — нагрузка исполнителей (total/open/done/overdue/avg_hours);
- report_sla — SLA-статистика по приоритетам (в срок / просрочено / процент);
- live_dashboard_metrics — открытых, просрочено, без исполнителя.

Чтобы тесты были детерминированы, мы вручную проставляем created_at/closed_at
через .update() — auto_now_add заполняет их «текущим временем», а нам
нужны конкретные даты в прошлом.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone as tz

import pytest
from django.utils import timezone

from core import models, reports


# =============================================================================
# Утилиты
# =============================================================================
class TestParseDate:
    def test_returns_date_for_iso_string(self):
        assert reports.parse_date("2026-05-29") == date(2026, 5, 29)

    def test_returns_none_for_empty(self):
        assert reports.parse_date(None) is None
        assert reports.parse_date("") is None

    def test_returns_none_for_invalid(self):
        assert reports.parse_date("not-a-date") is None
        assert reports.parse_date("2026-13-01") is None


class TestDefaultPeriod:
    def test_returns_last_30_days(self):
        date_from, date_to = reports.default_period()
        assert (date_to - date_from).days == 29
        # date_to — сегодня (по локали).
        assert date_to == timezone.localdate()


# =============================================================================
# report_by_period
# =============================================================================
def _set_created_at(req: models.Request, when: datetime) -> None:
    """Принудительно перезаписать created_at (auto_now_add игнорирует прямой save)."""
    models.Request.objects.filter(pk=req.pk).update(created_at=when)
    req.refresh_from_db()


def _set_closed_at(req: models.Request, when: datetime) -> None:
    models.Request.objects.filter(pk=req.pk).update(closed_at=when)
    req.refresh_from_db()


class TestReportByPeriod:
    def test_rows_length_matches_range(self, db):
        """Возвращается ровно (date_to - date_from + 1) строк, по одной на день."""
        d_from = date(2026, 1, 1)
        d_to = date(2026, 1, 7)
        result = reports.report_by_period(d_from, d_to)
        assert len(result["rows"]) == 7
        assert result["rows"][0]["date"] == d_from
        assert result["rows"][-1]["date"] == d_to

    def test_counts_created_per_day(self, make_request):
        """Заявки, созданные в разные дни, должны попасть в свои строки."""
        d_from = date(2026, 1, 1)
        d_to = date(2026, 1, 5)

        req1 = make_request()
        req2 = make_request()
        req3 = make_request()
        # Один в день 1, два в день 3.
        _set_created_at(req1, datetime(2026, 1, 1, 10, tzinfo=tz.utc))
        _set_created_at(req2, datetime(2026, 1, 3, 12, tzinfo=tz.utc))
        _set_created_at(req3, datetime(2026, 1, 3, 18, tzinfo=tz.utc))

        result = reports.report_by_period(d_from, d_to)
        rows_by_date = {r["date"]: r for r in result["rows"]}
        assert rows_by_date[date(2026, 1, 1)]["created"] == 1
        assert rows_by_date[date(2026, 1, 2)]["created"] == 0
        assert rows_by_date[date(2026, 1, 3)]["created"] == 2
        assert rows_by_date[date(2026, 1, 4)]["created"] == 0
        assert result["totals"]["created"] == 3

    def test_counts_closed_per_day(self, make_request, manager_user):
        """closed_at тоже должен учитываться корректно."""
        d_from = date(2026, 2, 1)
        d_to = date(2026, 2, 3)

        req = make_request()
        _set_closed_at(req, datetime(2026, 2, 2, 9, tzinfo=tz.utc))

        result = reports.report_by_period(d_from, d_to)
        rows_by_date = {r["date"]: r for r in result["rows"]}
        assert rows_by_date[date(2026, 2, 1)]["closed"] == 0
        assert rows_by_date[date(2026, 2, 2)]["closed"] == 1
        assert rows_by_date[date(2026, 2, 3)]["closed"] == 0
        assert result["totals"]["closed"] == 1

    def test_chart_structure(self, db):
        result = reports.report_by_period(date(2026, 1, 1), date(2026, 1, 3))
        assert "labels" in result["chart"]
        assert "created" in result["chart"]
        assert "closed" in result["chart"]
        assert len(result["chart"]["labels"]) == 3


# =============================================================================
# report_executors
# =============================================================================
class TestReportExecutors:
    def test_counts_assigned_total_open_done(
        self, make_request, executor_user, manager_user, statuses,
    ):
        # 2 открытых + 1 закрытый, все назначены на executor_user.
        a = make_request(assignee=executor_user)
        b = make_request(assignee=executor_user)
        c = make_request(assignee=executor_user)
        # c → done
        c.status = statuses["done"]
        c.closed_at = timezone.now()
        c.save()

        rows = reports.report_executors()
        # Найти строку с нашим исполнителем.
        row = next((r for r in rows if r["id"] == executor_user.id), None)
        assert row is not None
        assert row["total"] == 3
        assert row["open"] == 2
        assert row["done"] == 1

    def test_overdue_counted(
        self, make_request, executor_user,
    ):
        """Просроченное = открытое и due_date в прошлом."""
        req = make_request(assignee=executor_user)
        # Сделаем due_date в прошлом.
        models.Request.objects.filter(pk=req.pk).update(
            due_date=timezone.now() - timedelta(hours=1),
        )

        rows = reports.report_executors()
        row = next((r for r in rows if r["id"] == executor_user.id), None)
        assert row is not None
        assert row["overdue"] == 1

    def test_includes_only_executors_and_managers(
        self, executor_user, manager_user, operator_user,
    ):
        """В отчёт попадают только исполнители и менеджеры, оператор — нет."""
        rows = reports.report_executors()
        ids = {r["id"] for r in rows}
        assert executor_user.id in ids
        assert manager_user.id in ids
        # Оператор не должен попасть.
        assert operator_user.id not in ids


# =============================================================================
# report_sla
# =============================================================================
class TestReportSla:
    def test_in_time_when_closed_before_due(
        self, make_request, priorities, statuses,
    ):
        """closed_at <= due_date → засчитываем как 'в срок'."""
        req = make_request(priority=priorities["medium"])
        # due_date уже стоит = created_at + 24ч. Закроем за 1 час до due_date.
        models.Request.objects.filter(pk=req.pk).update(
            status=statuses["done"],
            closed_at=req.due_date - timedelta(hours=1),
        )
        result = reports.report_sla()
        row = next(r for r in result["rows"] if r["priority_code"] == "medium")
        assert row["in_time"] == 1
        assert row["overdue"] == 0
        assert row["sla_pct"] == 100.0

    def test_overdue_when_closed_after_due(
        self, make_request, priorities, statuses,
    ):
        """closed_at > due_date → 'просрочено'."""
        req = make_request(priority=priorities["high"])
        models.Request.objects.filter(pk=req.pk).update(
            status=statuses["done"],
            closed_at=req.due_date + timedelta(hours=2),
        )
        result = reports.report_sla()
        row = next(r for r in result["rows"] if r["priority_code"] == "high")
        assert row["in_time"] == 0
        assert row["overdue"] == 1
        assert row["sla_pct"] == 0.0

    def test_open_overdue_counted_separately(
        self, make_request, priorities,
    ):
        """Открытые, у которых уже просрочен due_date, идут в open_overdue."""
        req = make_request(priority=priorities["low"])
        models.Request.objects.filter(pk=req.pk).update(
            due_date=timezone.now() - timedelta(hours=1),
        )
        result = reports.report_sla()
        row = next(r for r in result["rows"] if r["priority_code"] == "low")
        assert row["open_overdue"] == 1
        # При этом total_closed (закрытых) — 0, потому что заявка не закрыта.
        assert row["total_closed"] == 0
        assert row["sla_pct"] is None

    def test_grand_totals(
        self, make_request, priorities, statuses,
    ):
        """Общий процент SLA = доля 'в срок' от всех закрытых."""
        # 1 в срок, 1 просрочена.
        a = make_request(priority=priorities["medium"])
        models.Request.objects.filter(pk=a.pk).update(
            status=statuses["done"],
            closed_at=a.due_date - timedelta(hours=1),
        )
        b = make_request(priority=priorities["medium"])
        models.Request.objects.filter(pk=b.pk).update(
            status=statuses["done"],
            closed_at=b.due_date + timedelta(hours=1),
        )

        result = reports.report_sla()
        assert result["totals"]["in_time"] == 1
        assert result["totals"]["overdue"] == 1
        assert result["totals"]["total_closed"] == 2
        assert result["totals"]["sla_pct"] == 50.0


# =============================================================================
# live_dashboard_metrics
# =============================================================================
class TestLiveDashboardMetrics:
    def test_open_total_counts_only_non_terminal(
        self, make_request, statuses,
    ):
        a = make_request()
        b = make_request()
        c = make_request()
        # c → done (терминальный, не должен попасть в open_total).
        c.status = statuses["done"]
        c.closed_at = timezone.now()
        c.save()

        m = reports.live_dashboard_metrics()
        assert m["open_total"] == 2

    def test_overdue_in_open_only(
        self, make_request, statuses,
    ):
        """Просроченное = открытое + due_date в прошлом. Закрытые не считаем."""
        a = make_request()
        models.Request.objects.filter(pk=a.pk).update(
            due_date=timezone.now() - timedelta(hours=1),
        )
        # Закрытая заявка с просроченным due_date в overdue не входит.
        b = make_request()
        b.status = statuses["done"]
        b.closed_at = timezone.now()
        b.save()
        models.Request.objects.filter(pk=b.pk).update(
            due_date=timezone.now() - timedelta(hours=1),
        )

        m = reports.live_dashboard_metrics()
        assert m["overdue"] == 1

    def test_unassigned_counts_only_open_no_assignee(
        self, make_request, executor_user, statuses,
    ):
        unassigned = make_request()
        assigned = make_request(assignee=executor_user)
        # Закрытая без исполнителя не должна попасть в unassigned.
        closed_unassigned = make_request()
        closed_unassigned.status = statuses["done"]
        closed_unassigned.closed_at = timezone.now()
        closed_unassigned.save()

        m = reports.live_dashboard_metrics()
        assert m["unassigned"] == 1

    def test_by_status_breakdown(
        self, make_request, statuses,
    ):
        """В разрезе по статусам — список с количеством на каждый ОТКРЫТЫЙ статус."""
        a = make_request()  # new
        b = make_request()
        b.status = statuses["in_progress"]
        b.save()

        m = reports.live_dashboard_metrics()
        codes = {row["status__code"]: row["cnt"] for row in m["by_status"]}
        assert codes.get("new") == 1
        assert codes.get("in_progress") == 1
