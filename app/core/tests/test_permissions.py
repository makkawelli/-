"""Тесты на права доступа (RBAC) и машину состояний (FSM).

Покрытие:
- can_create_request / can_edit_request / can_view_request / can_comment_request;
- can_view_reports / can_view_clients / can_edit_client;
- visible_requests_qs (исполнитель видит только свои);
- ALLOWED_TRANSITIONS (полная карта переходов FSM);
- can_transition с учётом ролей (исполнитель только свои; оператор не закрывает).
"""
from __future__ import annotations

import pytest

from core import permissions
from core.permissions import ALLOWED_TRANSITIONS


# =============================================================================
# RBAC: матрица «кто что может»
# =============================================================================
class TestCanCreateRequest:
    def test_admin_can(self, admin_user):
        assert permissions.can_create_request(admin_user)

    def test_manager_can(self, manager_user):
        assert permissions.can_create_request(manager_user)

    def test_operator_can(self, operator_user):
        assert permissions.can_create_request(operator_user)

    def test_executor_cannot(self, executor_user):
        assert not permissions.can_create_request(executor_user)

    def test_anonymous_cannot(self, db):
        from django.contrib.auth.models import AnonymousUser
        assert not permissions.can_create_request(AnonymousUser())


class TestCanEditRequest:
    @pytest.mark.parametrize("role_fixture", ["admin_user", "manager_user", "operator_user"])
    def test_staff_can_edit(self, role_fixture, request, make_request):
        user = request.getfixturevalue(role_fixture)
        req = make_request()
        assert permissions.can_edit_request(user, req)

    def test_executor_cannot_edit(self, executor_user, make_request):
        """Исполнитель не редактирует карточку — только статус и комменты."""
        req = make_request(assignee=executor_user)
        assert not permissions.can_edit_request(executor_user, req)


class TestCanViewRequest:
    def test_executor_sees_own_request(self, executor_user, make_request):
        req = make_request(assignee=executor_user)
        assert permissions.can_view_request(executor_user, req)

    def test_executor_does_not_see_others(self, executor_user, other_executor, make_request):
        """Исполнитель не должен видеть заявку, назначенную другому исполнителю."""
        req = make_request(assignee=other_executor)
        assert not permissions.can_view_request(executor_user, req)

    @pytest.mark.parametrize("role_fixture", ["admin_user", "manager_user", "operator_user"])
    def test_staff_sees_all_requests(self, role_fixture, request, executor_user, make_request):
        """Админ/менеджер/оператор видит любую заявку, в т. ч. назначенную другому."""
        user = request.getfixturevalue(role_fixture)
        req = make_request(assignee=executor_user)
        assert permissions.can_view_request(user, req)


class TestReportsAndClientsAccess:
    @pytest.mark.parametrize("role_fixture", ["admin_user", "manager_user"])
    def test_reports_allowed(self, role_fixture, request):
        user = request.getfixturevalue(role_fixture)
        assert permissions.can_view_reports(user)

    @pytest.mark.parametrize("role_fixture", ["operator_user", "executor_user"])
    def test_reports_denied(self, role_fixture, request):
        user = request.getfixturevalue(role_fixture)
        assert not permissions.can_view_reports(user)

    @pytest.mark.parametrize(
        "role_fixture",
        ["admin_user", "manager_user", "operator_user", "executor_user"],
    )
    def test_clients_visible_to_all_staff(self, role_fixture, request):
        user = request.getfixturevalue(role_fixture)
        assert permissions.can_view_clients(user)

    def test_executor_cannot_edit_clients(self, executor_user):
        """Исполнитель видит клиентов, но не редактирует."""
        assert permissions.can_view_clients(executor_user)
        assert not permissions.can_edit_client(executor_user)

    @pytest.mark.parametrize("role_fixture", ["admin_user", "manager_user", "operator_user"])
    def test_staff_can_edit_clients(self, role_fixture, request):
        user = request.getfixturevalue(role_fixture)
        assert permissions.can_edit_client(user)


# =============================================================================
# Видимость списка заявок
# =============================================================================
class TestVisibleRequestsQs:
    def test_executor_sees_only_own(
        self, executor_user, other_executor, make_request,
    ):
        own = make_request(assignee=executor_user, title="Своя")
        foreign = make_request(assignee=other_executor, title="Чужая")
        unassigned = make_request(title="Без исполнителя")

        qs = permissions.visible_requests_qs(executor_user)
        ids = set(qs.values_list("id", flat=True))
        assert own.id in ids
        assert foreign.id not in ids
        assert unassigned.id not in ids

    @pytest.mark.parametrize("role_fixture", ["admin_user", "manager_user", "operator_user"])
    def test_staff_sees_all(
        self, role_fixture, request, executor_user, other_executor, make_request,
    ):
        user = request.getfixturevalue(role_fixture)
        a = make_request(assignee=executor_user)
        b = make_request(assignee=other_executor)
        c = make_request()
        qs = permissions.visible_requests_qs(user)
        assert qs.filter(id__in=[a.id, b.id, c.id]).count() == 3


# =============================================================================
# FSM: полная карта переходов
# =============================================================================
class TestStateMachineMap:
    """Замораживаем форму ALLOWED_TRANSITIONS — это ключевая бизнес-логика."""

    def test_transitions_from_new(self):
        assert set(ALLOWED_TRANSITIONS["new"]) == {"in_progress", "cancelled"}

    def test_transitions_from_in_progress(self):
        assert set(ALLOWED_TRANSITIONS["in_progress"]) == {"on_hold", "review", "cancelled"}

    def test_transitions_from_on_hold(self):
        assert set(ALLOWED_TRANSITIONS["on_hold"]) == {"in_progress", "cancelled"}

    def test_transitions_from_review(self):
        assert set(ALLOWED_TRANSITIONS["review"]) == {"in_progress", "done"}

    def test_done_is_terminal(self):
        assert ALLOWED_TRANSITIONS["done"] == []

    def test_cancelled_is_terminal(self):
        assert ALLOWED_TRANSITIONS["cancelled"] == []


class TestAllowedTransitionsFor:
    def test_returns_correct_list(self, make_request):
        """Свежая заявка в статусе new → можно либо in_progress, либо cancelled."""
        req = make_request()
        assert set(permissions.allowed_transitions_for(req)) == {"in_progress", "cancelled"}


# =============================================================================
# can_transition: ролевые ограничения
# =============================================================================
class TestCanTransition:
    def test_target_must_be_allowed(self, manager_user, make_request):
        """Нельзя сразу из new в done — это запрещено картой переходов."""
        req = make_request()
        assert not permissions.can_transition(manager_user, req, "done")

    @pytest.mark.parametrize("role_fixture", ["admin_user", "manager_user"])
    def test_admin_and_manager_can_close(
        self, role_fixture, request, make_request, statuses,
    ):
        """Менеджер и админ могут закрывать заявку (review → done)."""
        user = request.getfixturevalue(role_fixture)
        req = make_request()
        # Сначала переведём в review через прямую правку — чтобы проверить именно done.
        req.status = statuses["review"]
        req.save()
        assert permissions.can_transition(user, req, "done")

    def test_operator_cannot_close(self, operator_user, make_request, statuses):
        """Оператор не имеет права закрывать заявку (done) — это решение менеджера."""
        req = make_request()
        req.status = statuses["review"]
        req.save()
        assert not permissions.can_transition(operator_user, req, "done")

    def test_operator_can_other_transitions(self, operator_user, make_request):
        """Но в in_progress / cancelled — может."""
        req = make_request()
        assert permissions.can_transition(operator_user, req, "in_progress")
        assert permissions.can_transition(operator_user, req, "cancelled")

    def test_executor_only_on_own(
        self, executor_user, other_executor, make_request,
    ):
        """Исполнитель меняет статус только своей заявки."""
        own = make_request(assignee=executor_user)
        foreign = make_request(assignee=other_executor)
        assert permissions.can_transition(executor_user, own, "in_progress")
        assert not permissions.can_transition(executor_user, foreign, "in_progress")
