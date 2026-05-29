"""Email-уведомления о ключевых событиях по заявкам.

Намеренно сделано **синхронно** — без Celery/Redis, чтобы не плодить
инфраструктуру в учебном проекте. Цена: каждый запрос на создание
заявки или смену статуса будет ждать ~200–500 мс на отправке SMTP.
В DEBUG-окружении письма пишутся в консоль (EMAIL_BACKEND настроен
в settings.py), поэтому никакого реального SMTP не требуется.

В production-варианте этот модуль легко переключается на асинхронный
вариант: тело каждой функции `notify_*` обернуть в `@shared_task`
из Celery, остальной код не меняется.

Особенности реализации:
- любой сбой при отправке логируется, но не прерывает основную
  бизнес-операцию (try/except внутри _send);
- не отправляется письмо, если адресат не имеет email — это
  вполне валидная ситуация (например, исполнитель без email).
"""
from __future__ import annotations

import logging
from typing import Iterable

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from . import models

logger = logging.getLogger(__name__)


def _absolute_url(path: str) -> str:
    """Сформировать абсолютный URL для писем.

    В DEBUG-режиме hardcode на http://127.0.0.1:8000.
    На проде нужно будет переопределить SITE_URL в settings.py.
    """
    base = getattr(settings, "SITE_URL", "http://127.0.0.1:8000").rstrip("/")
    return f"{base}{path}"


def _send(
    *,
    subject: str,
    template_name: str,
    context: dict,
    to: Iterable[str],
) -> bool:
    """Низкоуровневая отправка письма с plain-text и HTML-частями.

    template_name — имя без расширения; берёт <name>.txt и <name>.html.
    Возвращает True, если письмо ушло без исключения, иначе False.
    """
    recipients = [r for r in to if r]
    if not recipients:
        return False

    text_body = render_to_string(f"emails/{template_name}.txt", context)
    try:
        html_body = render_to_string(f"emails/{template_name}.html", context)
    except Exception:
        html_body = None

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients,
        )
        if html_body:
            msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=False)
        return True
    except Exception as exc:  # noqa: BLE001 — намеренно ловим всё
        logger.warning("Не удалось отправить email %r на %r: %s",
                       template_name, recipients, exc)
        return False


# =============================================================================
# Конкретные уведомления
# =============================================================================
def notify_request_created(req: models.Request) -> None:
    """Письмо клиенту при регистрации заявки."""
    if not req.client.email:
        return
    _send(
        subject=f"Заявка {req.number} зарегистрирована",
        template_name="request_created",
        context={
            "request": req,
            "client": req.client,
            "url": _absolute_url(f"/requests/{req.number}/"),
        },
        to=[req.client.email],
    )


def notify_request_assigned(req: models.Request) -> None:
    """Письмо исполнителю при назначении на заявку."""
    if not req.assignee or not req.assignee.email:
        return
    _send(
        subject=f"Вам назначена заявка {req.number}",
        template_name="request_assigned",
        context={
            "request": req,
            "assignee": req.assignee,
            "url": _absolute_url(f"/requests/{req.number}/"),
        },
        to=[req.assignee.email],
    )


def notify_status_changed(req: models.Request, old_status, new_status) -> None:
    """Письмо клиенту при смене статуса.

    Не отправляем для технических переходов на «Новая» (это и есть создание;
    отдельное письмо уже ушло из notify_request_created).
    """
    if new_status.code == "new":
        return
    if not req.client.email:
        return
    _send(
        subject=f"Заявка {req.number}: статус «{new_status.name}»",
        template_name="status_changed",
        context={
            "request": req,
            "client": req.client,
            "old_status": old_status,
            "new_status": new_status,
            "url": _absolute_url(f"/requests/{req.number}/"),
        },
        to=[req.client.email],
    )


def notify_comment_added(comment: models.Comment) -> None:
    """Письмо клиенту при появлении нового публичного комментария.

    Внутренние комментарии (is_internal=True) клиенту не показываются.
    """
    if comment.is_internal:
        return
    req = comment.request
    if not req.client.email:
        return
    _send(
        subject=f"Заявка {req.number}: новый комментарий",
        template_name="comment_added",
        context={
            "request": req,
            "client": req.client,
            "comment": comment,
            "url": _absolute_url(f"/requests/{req.number}/#comments"),
        },
        to=[req.client.email],
    )
