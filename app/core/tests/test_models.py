"""Тесты на уровне моделей и сервисной утилиты generate_request_number.

Проверяем:
- генератор сквозных номеров REQ-YYYY-NNNNNN;
- дефолтное значение JSONB-поля custom_fields = {};
- терминальные статусы (done, cancelled);
- __str__ ключевых сущностей (полезно для админки).
"""
from __future__ import annotations

import pytest
from django.utils import timezone

from core import models, services


# ---------------------------------------------------------------------------
# Генератор номера заявки
# ---------------------------------------------------------------------------
class TestRequestNumber:
    def test_first_number_is_000001(self, db):
        """Если в текущем году заявок нет — номер должен быть NNNNNN = 000001."""
        year = timezone.now().year
        assert services.generate_request_number() == f"REQ-{year}-000001"

    def test_increments_after_existing(
        self, make_request,
    ):
        """После уже созданной заявки номер должен инкрементироваться."""
        first = make_request()
        year = timezone.now().year
        assert first.number == f"REQ-{year}-000001"
        # Следующий вызов генератора (без записи в БД) должен дать 000002.
        assert services.generate_request_number() == f"REQ-{year}-000002"

    def test_pads_to_six_digits(self, make_request):
        """Формат должен быть с ведущими нулями до 6 знаков."""
        req = make_request()
        # Префикс REQ- + 4 цифры года + дефис + 6 цифр номера = 15 символов.
        assert len(req.number) == 15
        seq = req.number.split("-")[-1]
        assert seq.isdigit() and len(seq) == 6


# ---------------------------------------------------------------------------
# Дефолты Request
# ---------------------------------------------------------------------------
class TestRequestDefaults:
    def test_custom_fields_default_is_empty_dict(self, make_request):
        """custom_fields должно быть пустым словарём по умолчанию."""
        req = make_request()
        assert req.custom_fields == {}

    def test_custom_fields_preserved_on_create(self, make_request):
        """Переданные значения custom_fields должны сохраниться."""
        payload = {"vehicle_vin": "XYZ12345", "urgent": True}
        req = make_request(custom_fields=payload)
        req.refresh_from_db()
        assert req.custom_fields == payload

    def test_initial_status_is_new(self, make_request, statuses):
        """Свежесозданная заявка должна быть в статусе 'new'."""
        req = make_request()
        assert req.status == statuses["new"]

    def test_due_date_is_set_from_priority_sla(self, make_request, priorities):
        """due_date должен отстоять от created_at на priority.sla_hours."""
        req = make_request(priority=priorities["high"])  # 8 часов
        assert req.due_date is not None
        delta = req.due_date - req.created_at
        # Допустимая дельта расчёта — пара секунд, но значение точно ~8 ч.
        assert 7 * 3600 < delta.total_seconds() < 9 * 3600


# ---------------------------------------------------------------------------
# Терминальные статусы
# ---------------------------------------------------------------------------
class TestStatusTerminalFlag:
    def test_done_is_terminal(self, statuses):
        assert statuses["done"].is_terminal is True

    def test_cancelled_is_terminal(self, statuses):
        assert statuses["cancelled"].is_terminal is True

    def test_open_statuses_are_not_terminal(self, statuses):
        for code in ("new", "in_progress", "on_hold", "review"):
            assert statuses[code].is_terminal is False, f"{code} не должен быть терминальным"


# ---------------------------------------------------------------------------
# __str__ для админки
# ---------------------------------------------------------------------------
class TestStrRepresentations:
    def test_request_str(self, make_request):
        req = make_request(title="Починить принтер")
        assert req.number in str(req)
        assert "Починить принтер" in str(req)

    def test_employee_str_uses_full_name(self, manager_user):
        assert str(manager_user) == "Иванов Иван Иванович"

    def test_employee_str_falls_back_to_username(self, db, roles):
        u = models.Employee.objects.create_user(
            username="noname", password="x", full_name="",
        )
        u.role = roles["operator"]
        u.save()
        assert str(u) == "noname"

    def test_priority_str(self, priorities):
        assert str(priorities["critical"]) == "Критический"
