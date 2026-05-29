"""Тесты email-уведомлений.

Проверяем 4 события:
1. notify_request_created — клиенту при создании заявки;
2. notify_request_assigned — исполнителю при назначении;
3. notify_status_changed — клиенту при смене статуса (но НЕ в new);
4. notify_comment_added — клиенту при публичном комментарии
   (внутренний is_internal=True не отправляется).

Особенность: сервисный слой использует transaction.on_commit для отправки.
В обычных тестах с @pytest.mark.django_db (savepoint-режим) on_commit
не вызывается. Поэтому здесь либо берём transaction=True, либо вызываем
функции notify_* напрямую — оба подхода покрывают разные грани.
"""
from __future__ import annotations

import pytest
from django.core import mail

from core import notifications, services


# =============================================================================
# Прямые вызовы notify_* (юнит-уровень, без транзакций)
# =============================================================================
class TestNotifyRequestCreated:
    def test_sends_to_client_email(self, make_request, mailoutbox):
        req = make_request()
        mailoutbox.clear()  # очищаем письма, которые могли уйти при make_request
        notifications.notify_request_created(req)
        assert len(mailoutbox) == 1
        msg = mailoutbox[0]
        assert msg.to == [req.client.email]
        assert req.number in msg.subject

    def test_silent_when_no_client_email(
        self, db, service, priorities, operator_user, statuses,
    ):
        """Если у клиента не указан email — письмо не отправляется."""
        from core import models
        client_no_email = models.Client.objects.create(name="Без почты", email="")
        req = services.create_request(
            client=client_no_email,
            service=service,
            priority=priorities["medium"],
            title="x", description="",
            created_by=operator_user,
        )
        mail.outbox.clear()
        notifications.notify_request_created(req)
        assert len(mail.outbox) == 0


class TestNotifyRequestAssigned:
    def test_sends_to_assignee(
        self, make_request, executor_user, mailoutbox,
    ):
        req = make_request(assignee=executor_user)
        mailoutbox.clear()
        notifications.notify_request_assigned(req)
        assert len(mailoutbox) == 1
        assert mailoutbox[0].to == [executor_user.email]
        assert req.number in mailoutbox[0].subject

    def test_silent_when_no_assignee(self, make_request, mailoutbox):
        req = make_request()  # без assignee
        mailoutbox.clear()
        notifications.notify_request_assigned(req)
        assert len(mailoutbox) == 0


class TestNotifyStatusChanged:
    def test_sends_to_client_email(self, make_request, statuses, mailoutbox):
        req = make_request()
        mailoutbox.clear()
        notifications.notify_status_changed(
            req, statuses["new"], statuses["in_progress"],
        )
        assert len(mailoutbox) == 1
        assert mailoutbox[0].to == [req.client.email]
        assert "В работе" in mailoutbox[0].subject

    def test_skips_when_target_is_new(self, make_request, statuses, mailoutbox):
        """Переход в new — это создание заявки; отдельное письмо не нужно."""
        req = make_request()
        mailoutbox.clear()
        notifications.notify_status_changed(req, None, statuses["new"])
        assert len(mailoutbox) == 0


class TestNotifyCommentAdded:
    def test_public_comment_sends_to_client(
        self, make_request, operator_user, mailoutbox,
    ):
        req = make_request()
        comment = services.add_comment(
            request_obj=req, author=operator_user, text="Уточнение",
            is_internal=False,
        )
        mailoutbox.clear()
        notifications.notify_comment_added(comment)
        assert len(mailoutbox) == 1
        assert mailoutbox[0].to == [req.client.email]

    def test_internal_comment_does_not_send(
        self, make_request, operator_user, mailoutbox,
    ):
        """Внутренний комментарий клиенту не должен уходить."""
        req = make_request()
        comment = services.add_comment(
            request_obj=req, author=operator_user, text="Только для своих",
            is_internal=True,
        )
        mailoutbox.clear()
        notifications.notify_comment_added(comment)
        assert len(mailoutbox) == 0


# =============================================================================
# Интеграционный путь — через сервисы и реальные транзакции
# =============================================================================
@pytest.mark.django_db(transaction=True)
class TestServicesFireNotifications:
    """С transaction=True commit реально происходит, on_commit вызывается."""

    def test_create_request_sends_creation_email(
        self, client_record, service, priorities, operator_user, statuses,
    ):
        mail.outbox.clear()
        services.create_request(
            client=client_record,
            service=service,
            priority=priorities["medium"],
            title="Новая",
            description="",
            created_by=operator_user,
        )
        # Должно уйти ровно 1 письмо клиенту (assignee нет).
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == [client_record.email]

    def test_create_request_with_assignee_sends_two_emails(
        self,
        client_record, service, priorities, operator_user, executor_user,
        roles, statuses,
    ):
        mail.outbox.clear()
        services.create_request(
            client=client_record,
            service=service,
            priority=priorities["medium"],
            title="С исполнителем",
            description="",
            created_by=operator_user,
            assignee=executor_user,
        )
        # 1 клиенту + 1 исполнителю = 2.
        assert len(mail.outbox) == 2
        recipients = sorted(addr for m in mail.outbox for addr in m.to)
        assert recipients == sorted([client_record.email, executor_user.email])
