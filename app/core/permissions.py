"""Бизнес-правила доступа (RBAC).

Логика разграничения прав вынесена в отдельный модуль, чтобы во views.py
не загромождать код условиями. На каждое действие — отдельная функция,
которой удобно пользоваться и в шаблонах (через context), и в декораторах.

Базовая модель ролей:
    admin     — полный доступ;
    manager   — видит всё, может всё (кроме настроек системы);
    operator  — диспетчер: создаёт заявки, назначает исполнителей;
    executor  — исполнитель: видит только свои заявки;
    client    — клиент: пока в системе через UI не работает.
"""
from __future__ import annotations

from .models import Request


# ---------- Утилиты ----------------------------------------------------------

def _role(user) -> str | None:
    """Вернуть код роли пользователя или None."""
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser:
        return "admin"
    return user.role.code if getattr(user, "role_id", None) and user.role else None


# ---------- Полномочия на действия ------------------------------------------

def can_create_request(user) -> bool:
    """Создавать новые заявки могут оператор/менеджер/админ."""
    return _role(user) in {"admin", "manager", "operator"}


def can_edit_request(user, request_obj: Request) -> bool:
    """Редактировать карточку заявки могут оператор/менеджер/админ.

    Исполнитель не может править поля заявки — только менять статус
    и оставлять комментарии.
    """
    return _role(user) in {"admin", "manager", "operator"}


def can_view_request(user, request_obj: Request) -> bool:
    """Видеть конкретную заявку.

    Исполнитель видит только свои назначенные.
    Остальные роли видят все.
    """
    role = _role(user)
    if role in {"admin", "manager", "operator"}:
        return True
    if role == "executor":
        return request_obj.assignee_id == user.id
    return False


def can_comment_request(user, request_obj: Request) -> bool:
    """Оставлять комментарии могут все, кто видит заявку."""
    return can_view_request(user, request_obj)


# ---------- Видимость списка заявок -----------------------------------------

def visible_requests_qs(user):
    """Queryset заявок, видимых пользователю.

    Используется во всех list/detail-вьюхах для единообразия фильтрации.
    """
    qs = Request.objects.select_related(
        "client", "service", "status", "priority", "assignee", "created_by",
    )
    role = _role(user)
    if role in {"admin", "manager", "operator"}:
        return qs
    if role == "executor":
        return qs.filter(assignee=user)
    return qs.none()


# ---------- Переходы статусов -----------------------------------------------

# Машина состояний жизненного цикла заявки.
# Ключ — код текущего статуса; значение — список кодов, в которые можно перейти.
ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    "new":         ["in_progress", "cancelled"],
    "in_progress": ["on_hold", "review", "cancelled"],
    "on_hold":     ["in_progress", "cancelled"],
    "review":      ["in_progress", "done"],   # либо вернуть на доработку, либо принять
    "done":        [],                         # терминальный
    "cancelled":   [],                         # терминальный
}


def allowed_transitions_for(request_obj: Request) -> list[str]:
    """Возвращает список кодов статусов, в которые можно перейти из текущего."""
    return ALLOWED_TRANSITIONS.get(request_obj.status.code, [])


def can_transition(user, request_obj: Request, target_status_code: str) -> bool:
    """Может ли пользователь перевести заявку в указанный статус.

    1. Целевой статус должен быть в списке разрешённых из текущего.
    2. Менеджер/админ — могут всегда.
    3. Оператор — может всё, кроме закрытия (done) — это привилегия менеджера.
    4. Исполнитель — может менять статус только своей заявки.
    """
    if target_status_code not in allowed_transitions_for(request_obj):
        return False

    role = _role(user)
    if role in {"admin", "manager"}:
        return True
    if role == "operator":
        # Оператор не закрывает заявку — это решение менеджера.
        return target_status_code != "done"
    if role == "executor":
        return request_obj.assignee_id == user.id
    return False
