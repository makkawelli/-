"""Тесты сервисного слоя (бизнес-операций).

Проверяем три ключевые операции:
- create_request: создаёт заявку + StatusHistory("создана") + AuditLog("create");
- transition_request: меняет статус, ведёт closed_at для терминальных,
  пишет StatusHistory(from→to) + AuditLog("status_change");
- add_comment: создаёт комментарий + AuditLog("comment").

Уведомления (on_commit) тестируются отдельно в test_notifications.py.
"""
from __future__ import annotations

import pytest
from django.utils import timezone

from core import models, services


# =============================================================================
# create_request
# =============================================================================
class TestCreateRequest:
    def test_creates_request_with_status_new(
        self, db, client_record, service, priorities, operator_user, statuses,
    ):
        req = services.create_request(
            client=client_record,
            service=service,
            priority=priorities["medium"],
            title="Починить принтер",
            description="Не печатает.",
            created_by=operator_user,
        )
        assert req.pk is not None
        assert req.status == statuses["new"]
        assert req.title == "Починить принтер"
        assert req.created_by == operator_user
        assert req.number.startswith(f"REQ-{timezone.now().year}-")

    def test_writes_status_history_with_status_from_none(self, make_request):
        """При создании в истории должна появиться запись status_from=None → status_to=new."""
        req = make_request()
        history = list(req.status_history.all())
        assert len(history) == 1
        rec = history[0]
        assert rec.status_from is None
        assert rec.status_to.code == "new"
        assert rec.changed_by == req.created_by

    def test_writes_audit_log_create(self, make_request):
        log = models.AuditLog.objects.filter(
            action="create", entity_type="request",
        ).order_by("-id").first()
        # На момент вызова базы ещё нет записи — создаём, проверяем.
        req = make_request()
        log = models.AuditLog.objects.filter(
            action="create", entity_type="request", entity_id=req.id,
        ).first()
        assert log is not None
        assert log.actor == req.created_by
        assert log.payload["number"] == req.number

    def test_due_date_uses_priority_sla(
        self, db, client_record, service, priorities, operator_user, statuses,
    ):
        """Срок выполнения = created_at + priority.sla_hours."""
        before = timezone.now()
        req = services.create_request(
            client=client_record,
            service=service,
            priority=priorities["critical"],  # SLA 4 часа
            title="x", description="",
            created_by=operator_user,
        )
        delta = (req.due_date - before).total_seconds() / 3600
        # Должно быть около 4 часов с запасом на время выполнения теста.
        assert 3.99 < delta < 4.01

    def test_custom_fields_persisted(self, make_request):
        payload = {"vehicle_vin": "ABC123", "is_urgent": True}
        req = make_request(custom_fields=payload)
        req.refresh_from_db()
        assert req.custom_fields == payload

    def test_assignee_can_be_set_on_create(self, make_request, executor_user):
        req = make_request(assignee=executor_user)
        assert req.assignee == executor_user


# =============================================================================
# transition_request
# =============================================================================
class TestTransitionRequest:
    def test_updates_status(self, make_request, manager_user, statuses):
        req = make_request()
        services.transition_request(
            request_obj=req, to_status_code="in_progress",
            changed_by=manager_user,
        )
        req.refresh_from_db()
        assert req.status == statuses["in_progress"]

    def test_writes_status_history(self, make_request, manager_user, statuses):
        req = make_request()
        services.transition_request(
            request_obj=req, to_status_code="in_progress",
            changed_by=manager_user, comment="Берём в работу",
        )
        # 1 запись на создание + 1 на переход = 2.
        history = list(req.status_history.order_by("changed_at"))
        assert len(history) == 2
        last = history[-1]
        assert last.status_from == statuses["new"]
        assert last.status_to == statuses["in_progress"]
        assert last.changed_by == manager_user
        assert last.comment == "Берём в работу"

    def test_writes_audit_log_status_change(self, make_request, manager_user):
        req = make_request()
        services.transition_request(
            request_obj=req, to_status_code="in_progress",
            changed_by=manager_user,
        )
        log = (
            models.AuditLog.objects
            .filter(action="status_change", entity_id=req.id)
            .order_by("-id").first()
        )
        assert log is not None
        assert log.actor == manager_user
        assert log.payload["from"] == "new"
        assert log.payload["to"] == "in_progress"

    def test_sets_closed_at_on_terminal(
        self, make_request, manager_user, statuses,
    ):
        """Перевод в done должен проставить closed_at."""
        req = make_request()
        # Сначала через FSM-валидный маршрут: new → in_progress → review → done.
        for code in ("in_progress", "review", "done"):
            services.transition_request(
                request_obj=req, to_status_code=code, changed_by=manager_user,
            )
        req.refresh_from_db()
        assert req.status == statuses["done"]
        assert req.closed_at is not None

    def test_sets_closed_at_on_cancelled(
        self, make_request, manager_user, statuses,
    ):
        """Cancelled — тоже терминальный, closed_at должен проставиться."""
        req = make_request()
        services.transition_request(
            request_obj=req, to_status_code="cancelled", changed_by=manager_user,
        )
        req.refresh_from_db()
        assert req.closed_at is not None

    def test_clears_closed_at_when_reopened(
        self, make_request, manager_user, statuses,
    ):
        """Если из терминального возвращают в открытый — closed_at сбросить.

        Хотя FSM такого не разрешает (done — терминальный), сервис должен
        корректно работать на случай, если смена статуса делается напрямую
        (например, админом из shell).
        """
        req = make_request()
        # Симулируем закрытое состояние.
        req.status = statuses["done"]
        req.closed_at = timezone.now()
        req.save()
        # Возвращаем в работу — сервис должен сбросить closed_at.
        services.transition_request(
            request_obj=req, to_status_code="in_progress", changed_by=manager_user,
        )
        req.refresh_from_db()
        assert req.closed_at is None


# =============================================================================
# add_comment
# =============================================================================
class TestAddComment:
    def test_creates_comment(self, make_request, operator_user):
        req = make_request()
        c = services.add_comment(
            request_obj=req, author=operator_user, text="Уточнили детали.",
        )
        assert c.pk is not None
        assert c.request == req
        assert c.author == operator_user
        assert c.text == "Уточнили детали."
        assert c.is_internal is False

    def test_internal_flag(self, make_request, operator_user):
        req = make_request()
        c = services.add_comment(
            request_obj=req, author=operator_user, text="Внутр.",
            is_internal=True,
        )
        assert c.is_internal is True

    def test_writes_audit_log(self, make_request, operator_user):
        req = make_request()
        c = services.add_comment(
            request_obj=req, author=operator_user, text="hi",
        )
        log = (
            models.AuditLog.objects
            .filter(action="comment", entity_id=req.id)
            .order_by("-id").first()
        )
        assert log is not None
        assert log.actor == operator_user
        assert log.payload["comment_id"] == c.id


# =============================================================================
# Утилита calculate_due_date
# =============================================================================
class TestCalculateDueDate:
    def test_adds_sla_hours_to_start(self, priorities):
        from datetime import datetime, timezone as tz
        start = datetime(2026, 1, 1, 12, 0, tzinfo=tz.utc)
        due = services.calculate_due_date(priorities["medium"], start=start)
        # medium SLA = 24 часа.
        delta = (due - start).total_seconds() / 3600
        assert delta == 24

    def test_uses_now_by_default(self, priorities):
        before = timezone.now()
        due = services.calculate_due_date(priorities["high"])  # 8 часов
        after = timezone.now()
        # due должно быть в окрестности now + 8h.
        from datetime import timedelta
        assert before + timedelta(hours=8) - timedelta(seconds=2) <= due
        assert due <= after + timedelta(hours=8) + timedelta(seconds=2)
