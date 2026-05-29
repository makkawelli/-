"""Фикстуры pytest для тестов приложения core.

Идея: один раз готовим справочники (роли, статусы, приоритеты, услуги),
затем создаём по одному пользователю на каждую роль. Этим набором
покрывается ~95% всех сценариев тестирования.

Фикстуры с db-зависимостью НЕ имеют scope="session" (pytest-django это не
позволяет с обычным @pytest.mark.django_db) — они пересоздаются на каждый
тест. Это медленнее, но проще и предсказуемее.
"""
from __future__ import annotations

import pytest

from core import models


# =============================================================================
# СПРАВОЧНИКИ
# =============================================================================
@pytest.fixture
def roles(db) -> dict[str, models.Role]:
    """Все 5 ролей системы."""
    return {
        code: models.Role.objects.create(code=code, name=name)
        for code, name in [
            ("admin", "Администратор"),
            ("manager", "Менеджер"),
            ("operator", "Оператор"),
            ("executor", "Исполнитель"),
            ("client", "Клиент"),
        ]
    }


@pytest.fixture
def statuses(db) -> dict[str, models.Status]:
    """Все 6 статусов с правильными терминальными флагами."""
    data = [
        ("new", "Новая", 10, False),
        ("in_progress", "В работе", 20, False),
        ("on_hold", "Приостановлена", 30, False),
        ("review", "На проверке", 40, False),
        ("done", "Выполнена", 50, True),
        ("cancelled", "Отменена", 60, True),
    ]
    return {
        code: models.Status.objects.create(
            code=code, name=name, order_num=order, is_terminal=term,
        )
        for code, name, order, term in data
    }


@pytest.fixture
def priorities(db) -> dict[str, models.Priority]:
    """4 приоритета с разным SLA."""
    data = [
        ("low", "Низкий", 72),
        ("medium", "Средний", 24),
        ("high", "Высокий", 8),
        ("critical", "Критический", 4),
    ]
    return {
        code: models.Priority.objects.create(code=code, name=name, sla_hours=sla)
        for code, name, sla in data
    }


@pytest.fixture
def service(db) -> models.Service:
    """Одна услуга для подавляющего большинства тестов."""
    return models.Service.objects.create(
        name="Консультация", default_duration_hours=2, is_active=True,
    )


@pytest.fixture
def team(db) -> models.Team:
    """Одна группа исполнителей."""
    return models.Team.objects.create(name="Поддержка 1-й линии")


# =============================================================================
# ПОЛЬЗОВАТЕЛИ ВСЕХ РОЛЕЙ
# =============================================================================
def _make_employee(*, username: str, email: str, full_name: str, role) -> models.Employee:
    user = models.Employee.objects.create_user(
        username=username,
        email=email,
        password="testpass123",
        full_name=full_name,
    )
    user.role = role
    user.save()
    return user


@pytest.fixture
def admin_user(db, roles) -> models.Employee:
    """Суперпользователь + роль admin."""
    user = models.Employee.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="testpass123",
    )
    user.full_name = "Администратор Системный"
    user.role = roles["admin"]
    user.save()
    return user


@pytest.fixture
def manager_user(db, roles) -> models.Employee:
    return _make_employee(
        username="manager",
        email="manager@example.com",
        full_name="Иванов Иван Иванович",
        role=roles["manager"],
    )


@pytest.fixture
def operator_user(db, roles) -> models.Employee:
    return _make_employee(
        username="operator",
        email="operator@example.com",
        full_name="Петрова Мария Сергеевна",
        role=roles["operator"],
    )


@pytest.fixture
def executor_user(db, roles) -> models.Employee:
    return _make_employee(
        username="executor1",
        email="executor1@example.com",
        full_name="Сидоров Алексей Викторович",
        role=roles["executor"],
    )


@pytest.fixture
def other_executor(db, roles) -> models.Employee:
    """Второй исполнитель — нужен для проверки видимости 'только своих'."""
    return _make_employee(
        username="executor2",
        email="executor2@example.com",
        full_name="Кузнецов Дмитрий Олегович",
        role=roles["executor"],
    )


@pytest.fixture
def client_record(db) -> models.Client:
    """Клиент-контрагент с email — на него уходят уведомления."""
    return models.Client.objects.create(
        name='ООО "Ромашка"',
        contact_person="Семёнов Пётр",
        phone="+7 999 000-11-22",
        email="client@example.com",
    )


# =============================================================================
# СОЗДАНИЕ ЗАЯВКИ ОДНОЙ КОМАНДОЙ
# =============================================================================
@pytest.fixture
def make_request(db, client_record, service, statuses, priorities, operator_user):
    """Фабрика заявок. Использование:

        req = make_request()
        req = make_request(assignee=executor_user, status="in_progress")
    """
    from core import services

    def _factory(**kwargs):
        defaults = dict(
            client=client_record,
            service=service,
            priority=priorities["medium"],
            title="Тестовая заявка",
            description="Описание для теста.",
            created_by=operator_user,
            assignee=None,
            custom_fields=None,
        )
        # Возможность переопределить статус (для тестов отчётов).
        target_status_code = kwargs.pop("status", None)
        defaults.update(kwargs)
        req = services.create_request(**defaults)
        if target_status_code and target_status_code != "new":
            req.status = statuses[target_status_code]
            if statuses[target_status_code].is_terminal and req.closed_at is None:
                from django.utils import timezone
                req.closed_at = timezone.now()
            req.save(update_fields=["status", "closed_at"])
        return req

    return _factory
