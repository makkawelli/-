"""Сервисный слой — бизнес-операции над сущностями.

Отделение бизнес-логики от views позволяет:
- проще тестировать логику отдельно от HTTP-уровня;
- переиспользовать одни и те же операции в management-командах,
  REST-API в будущем, периодических задачах.
"""
from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from . import models, notifications


# =============================================================================
# Заявки
# =============================================================================
def generate_request_number() -> str:
    """Сгенерировать сквозной номер заявки в формате REQ-YYYY-NNNNNN.

    Берёт максимальный номер за текущий год и инкрементирует.
    Если в году ещё не было заявок — начинает с 000001.
    """
    year = timezone.now().year
    prefix = f"REQ-{year}-"
    last = (
        models.Request.objects
        .filter(number__startswith=prefix)
        .order_by("-number")
        .first()
    )
    if last:
        try:
            seq = int(last.number.split("-")[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:06d}"


def calculate_due_date(priority, start=None):
    """Рассчитать срок выполнения заявки по SLA приоритета."""
    start = start or timezone.now()
    return start + timedelta(hours=priority.sla_hours)


@transaction.atomic
def create_request(*, client, service, priority, title, description,
                   created_by, assignee=None, custom_fields=None):
    """Создать заявку с автогенерацией номера, due_date и записью в историю."""
    new_status = models.Status.objects.get(code="new")
    req = models.Request.objects.create(
        number=generate_request_number(),
        client=client,
        service=service,
        priority=priority,
        status=new_status,
        title=title,
        description=description,
        created_by=created_by,
        assignee=assignee,
        due_date=calculate_due_date(priority),
        custom_fields=custom_fields or {},
    )
    # Запись истории "создана".
    models.StatusHistory.objects.create(
        request=req,
        status_from=None,
        status_to=new_status,
        changed_by=created_by,
        comment="Заявка создана.",
    )
    # Аудит-журнал.
    models.AuditLog.objects.create(
        actor=created_by,
        action="create",
        entity_type="request",
        entity_id=req.id,
        payload={"number": req.number, "title": req.title},
    )

    # Уведомления (отправляются после COMMIT, чтобы не уйти впустую при rollback).
    transaction.on_commit(lambda: notifications.notify_request_created(req))
    if req.assignee:
        transaction.on_commit(lambda: notifications.notify_request_assigned(req))

    return req


@transaction.atomic
def transition_request(*, request_obj, to_status_code: str, changed_by,
                       comment: str = ""):
    """Перевести заявку в новый статус с записью в историю.

    Проверки разрешённости перехода — на стороне views (через permissions).
    Здесь — только механика.
    """
    new_status = models.Status.objects.get(code=to_status_code)
    old_status = request_obj.status

    request_obj.status = new_status
    if new_status.is_terminal and request_obj.closed_at is None:
        request_obj.closed_at = timezone.now()
    elif not new_status.is_terminal:
        request_obj.closed_at = None
    request_obj.save(update_fields=["status", "closed_at", "updated_at"])

    models.StatusHistory.objects.create(
        request=request_obj,
        status_from=old_status,
        status_to=new_status,
        changed_by=changed_by,
        comment=comment,
    )
    models.AuditLog.objects.create(
        actor=changed_by,
        action="status_change",
        entity_type="request",
        entity_id=request_obj.id,
        payload={
            "number": request_obj.number,
            "from": old_status.code,
            "to": new_status.code,
        },
    )

    # Уведомление клиенту о смене статуса.
    transaction.on_commit(
        lambda: notifications.notify_status_changed(request_obj, old_status, new_status)
    )

    return request_obj


@transaction.atomic
def add_comment(*, request_obj, author, text: str, is_internal: bool = False):
    """Добавить комментарий к заявке."""
    comment = models.Comment.objects.create(
        request=request_obj,
        author=author,
        text=text,
        is_internal=is_internal,
    )
    models.AuditLog.objects.create(
        actor=author,
        action="comment",
        entity_type="request",
        entity_id=request_obj.id,
        payload={"number": request_obj.number, "comment_id": comment.id},
    )

    # Уведомление клиенту (только для публичных комментариев — внутренние
    # отсекаются в notify_comment_added).
    transaction.on_commit(lambda: notifications.notify_comment_added(comment))

    return comment
