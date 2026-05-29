"""ORM-модели приложения core.

Соответствуют datalogical-схеме из artifacts/02_database/datalogical_schema.md
и SQL-скрипту artifacts/02_database/schema.sql.

Все модели имеют русские verbose_name — это нужно, чтобы админка
Django отображала названия таблиц и полей по-русски.
"""
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models

# GIN-индекс — фича PostgreSQL. На SQLite (используется в тестах) его нет,
# поэтому добавляем индекс к Request.Meta.indexes только если активный
# движок БД — PostgreSQL. Это позволяет крутить тесты на SQLite без
# отдельных миграций для тестовой БД.
_USING_POSTGRES = "postgresql" in settings.DATABASES["default"]["ENGINE"]
if _USING_POSTGRES:
    from django.contrib.postgres.indexes import GinIndex


# =============================================================================
# 1. СПРАВОЧНИКИ
# =============================================================================
class Role(models.Model):
    """Роль пользователя в системе.

    Используется для ролевого разграничения доступа (RBAC).
    Базовые коды: admin, manager, operator, executor, client.
    """
    code = models.CharField("Код", max_length=32, unique=True,
                            help_text="Машинный идентификатор: admin, manager, operator, executor, client")
    name = models.CharField("Название", max_length=64)

    class Meta:
        db_table = "role"
        verbose_name = "Роль"
        verbose_name_plural = "Роли"
        ordering = ["id"]

    def __str__(self) -> str:
        return self.name


class Service(models.Model):
    """Услуга, по которой может быть открыта заявка."""
    name = models.CharField("Название", max_length=128)
    description = models.TextField("Описание", blank=True)
    default_duration_hours = models.PositiveIntegerField(
        "Плановое время выполнения, ч",
        null=True, blank=True,
    )
    is_active = models.BooleanField("Активна", default=True)

    class Meta:
        db_table = "service"
        verbose_name = "Услуга"
        verbose_name_plural = "Услуги"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Status(models.Model):
    """Статус заявки. Реализует машину состояний жизненного цикла."""
    code = models.CharField("Код", max_length=32, unique=True)
    name = models.CharField("Название", max_length=64)
    order_num = models.PositiveSmallIntegerField("Порядок", default=100)
    is_terminal = models.BooleanField(
        "Финальный статус", default=False,
        help_text="Если True — заявка считается закрытой при переходе в этот статус",
    )

    class Meta:
        db_table = "status"
        verbose_name = "Статус"
        verbose_name_plural = "Статусы"
        ordering = ["order_num"]

    def __str__(self) -> str:
        return self.name


class Priority(models.Model):
    """Приоритет заявки и норматив SLA."""
    code = models.CharField("Код", max_length=16, unique=True)
    name = models.CharField("Название", max_length=32)
    sla_hours = models.PositiveIntegerField(
        "Норматив SLA, ч",
        help_text="Норматив выполнения: насколько быстро заявка должна быть закрыта",
    )

    class Meta:
        db_table = "priority"
        verbose_name = "Приоритет"
        verbose_name_plural = "Приоритеты"
        ordering = ["sla_hours"]

    def __str__(self) -> str:
        return self.name


class Team(models.Model):
    """Группа исполнителей. Используется для маршрутизации заявок."""
    name = models.CharField("Название", max_length=128, unique=True)

    class Meta:
        db_table = "team"
        verbose_name = "Группа исполнителей"
        verbose_name_plural = "Группы исполнителей"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


# =============================================================================
# 2. ПОЛЬЗОВАТЕЛИ И КЛИЕНТЫ
# =============================================================================
class Employee(AbstractUser):
    """Сотрудник = пользователь системы.

    Наследуется от django.contrib.auth.AbstractUser, поэтому из коробки
    получает поля: username, password (хеш), email, first_name, last_name,
    is_active, is_staff, is_superuser, last_login, date_joined.

    Сверху мы добавляем наши доменные поля: должность, роль, группы.
    """
    full_name = models.CharField("ФИО", max_length=255, blank=True)
    position = models.CharField("Должность", max_length=128, blank=True)
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        null=True, blank=True,
        verbose_name="Роль",
    )
    teams = models.ManyToManyField(
        Team,
        blank=True,
        verbose_name="Группы исполнителей",
        related_name="members",
    )

    class Meta:
        db_table = "employee"
        verbose_name = "Сотрудник"
        verbose_name_plural = "Сотрудники"
        ordering = ["full_name", "username"]

    def __str__(self) -> str:
        return self.full_name or self.username


class Client(models.Model):
    """Клиент (контрагент)."""
    name = models.CharField("Наименование", max_length=255)
    contact_person = models.CharField("Контактное лицо", max_length=255, blank=True)
    phone = models.CharField("Телефон", max_length=32, blank=True)
    email = models.EmailField("Email", blank=True)
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)

    class Meta:
        db_table = "client"
        verbose_name = "Клиент"
        verbose_name_plural = "Клиенты"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["phone"]),
            models.Index(fields=["email"]),
        ]

    def __str__(self) -> str:
        return self.name


# =============================================================================
# 3. ЯДРО: ЗАЯВКИ
# =============================================================================
class Request(models.Model):
    """Заявка на обслуживание — центральная сущность системы.

    Поле custom_fields реализует low-code-конструктор:
    значения пользовательских полей (описанных в FieldDefinition)
    хранятся в JSONB, а схема — в отдельной таблице.
    """
    number = models.CharField("Номер", max_length=32, unique=True,
                              help_text="Сквозной номер вида REQ-2026-000123")
    client = models.ForeignKey(
        Client, on_delete=models.PROTECT,
        verbose_name="Клиент",
        related_name="requests",
    )
    service = models.ForeignKey(
        Service, on_delete=models.PROTECT,
        verbose_name="Услуга",
        related_name="requests",
    )
    status = models.ForeignKey(
        Status, on_delete=models.PROTECT,
        verbose_name="Статус",
        related_name="requests",
    )
    priority = models.ForeignKey(
        Priority, on_delete=models.PROTECT,
        verbose_name="Приоритет",
        related_name="requests",
    )
    assignee = models.ForeignKey(
        Employee, on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Исполнитель",
        related_name="assigned_requests",
    )
    created_by = models.ForeignKey(
        Employee, on_delete=models.PROTECT,
        verbose_name="Кем создана",
        related_name="created_requests",
    )
    title = models.CharField("Краткое описание", max_length=255)
    description = models.TextField("Подробное описание", blank=True)
    due_date = models.DateTimeField("Срок выполнения", null=True, blank=True)
    closed_at = models.DateTimeField("Дата закрытия", null=True, blank=True)
    custom_fields = models.JSONField(
        "Пользовательские поля",
        default=dict, blank=True,
        help_text="Значения low-code-полей (описания см. в «Конструкторе полей»)",
    )
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    updated_at = models.DateTimeField("Дата изменения", auto_now=True)

    class Meta:
        db_table = "request"
        verbose_name = "Заявка"
        verbose_name_plural = "Заявки"
        ordering = ["-created_at"]
        # GIN-индекс по custom_fields добавляется только под PostgreSQL
        # (см. _USING_POSTGRES в начале файла). Это нужно, чтобы фильтры
        # по low-code-полям были быстрыми без отдельных миграций.
        indexes = (
            [GinIndex(fields=["custom_fields"], name="idx_request_custom_gin")]
            if _USING_POSTGRES else []
        )

    def __str__(self) -> str:
        return f"{self.number} - {self.title}"


# =============================================================================
# 4. КОММЕНТАРИИ, ВЛОЖЕНИЯ, ИСТОРИЯ
# =============================================================================
class Comment(models.Model):
    """Комментарий к заявке (внутренняя или клиентская переписка)."""
    request = models.ForeignKey(
        Request, on_delete=models.CASCADE,
        verbose_name="Заявка",
        related_name="comments",
    )
    author = models.ForeignKey(
        Employee, on_delete=models.PROTECT,
        verbose_name="Автор",
    )
    text = models.TextField("Текст")
    is_internal = models.BooleanField(
        "Внутренний", default=False,
        help_text="Если True - комментарий не показывается клиенту",
    )
    created_at = models.DateTimeField("Дата", auto_now_add=True)

    class Meta:
        db_table = "comment"
        verbose_name = "Комментарий"
        verbose_name_plural = "Комментарии"
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Комментарий к {self.request.number}"


class Attachment(models.Model):
    """Файловое вложение к заявке."""
    request = models.ForeignKey(
        Request, on_delete=models.CASCADE,
        verbose_name="Заявка",
        related_name="attachments",
    )
    file = models.FileField("Файл", upload_to="attachments/%Y/%m/")
    file_name = models.CharField("Имя файла", max_length=255)
    file_size = models.PositiveBigIntegerField("Размер, байт")
    mime_type = models.CharField("MIME-тип", max_length=128, blank=True)
    uploaded_by = models.ForeignKey(
        Employee, on_delete=models.PROTECT,
        verbose_name="Загрузил",
    )
    uploaded_at = models.DateTimeField("Дата загрузки", auto_now_add=True)

    class Meta:
        db_table = "attachment"
        verbose_name = "Вложение"
        verbose_name_plural = "Вложения"
        ordering = ["-uploaded_at"]

    def __str__(self) -> str:
        return self.file_name


class StatusHistory(models.Model):
    """Запись об изменении статуса заявки.

    Создаётся автоматически в сервисном слое при каждой смене статуса.
    Позволяет восстановить полную историю заявки.
    """
    request = models.ForeignKey(
        Request, on_delete=models.CASCADE,
        verbose_name="Заявка",
        related_name="status_history",
    )
    status_from = models.ForeignKey(
        Status, on_delete=models.PROTECT,
        null=True, blank=True,
        verbose_name="Из статуса",
        related_name="+",
        help_text="NULL - для записи о регистрации заявки",
    )
    status_to = models.ForeignKey(
        Status, on_delete=models.PROTECT,
        verbose_name="В статус",
        related_name="+",
    )
    changed_by = models.ForeignKey(
        Employee, on_delete=models.PROTECT,
        verbose_name="Кем изменён",
    )
    comment = models.TextField("Причина / комментарий", blank=True)
    changed_at = models.DateTimeField("Дата изменения", auto_now_add=True)

    class Meta:
        db_table = "status_history"
        verbose_name = "Запись истории статусов"
        verbose_name_plural = "История статусов"
        ordering = ["changed_at"]

    def __str__(self) -> str:
        if self.status_from:
            return f"{self.request.number}: {self.status_from} -> {self.status_to}"
        return f"{self.request.number}: создана со статусом {self.status_to}"


# =============================================================================
# 5. МАРШРУТИЗАЦИЯ И LOW-CODE КОНСТРУКТОР
# =============================================================================
class RoutingRule(models.Model):
    """Правило автоматической маршрутизации заявки на группу исполнителей."""
    service = models.ForeignKey(
        Service, on_delete=models.CASCADE,
        verbose_name="Услуга",
    )
    team = models.ForeignKey(
        Team, on_delete=models.CASCADE,
        verbose_name="Группа исполнителей",
    )
    priority_order = models.PositiveSmallIntegerField(
        "Приоритет применения", default=100,
        help_text="Чем меньше - тем раньше применяется правило",
    )
    is_active = models.BooleanField("Активно", default=True)

    class Meta:
        db_table = "routing_rule"
        verbose_name = "Правило маршрутизации"
        verbose_name_plural = "Правила маршрутизации"
        unique_together = [("service", "team")]
        ordering = ["priority_order"]

    def __str__(self) -> str:
        return f"{self.service} -> {self.team}"


class FieldDefinition(models.Model):
    """Описание пользовательского поля карточки заявки.

    Это и есть low-code-механизм: администратор через админку
    создаёт здесь запись (например, code='vehicle_vin', label='VIN автомобиля',
    field_type='text'), и в карточке заявки автоматически появляется
    соответствующее поле формы. Значения сохраняются в Request.custom_fields.
    """

    class FieldType(models.TextChoices):
        TEXT = "text", "Текст (одна строка)"
        TEXTAREA = "textarea", "Многострочный текст"
        NUMBER = "number", "Число"
        DATE = "date", "Дата"
        SELECT = "select", "Список (выбор одного)"
        CHECKBOX = "checkbox", "Флажок (да/нет)"

    code = models.CharField(
        "Код", max_length=64, unique=True,
        help_text="Латиницей, без пробелов. Будет ключом в JSON.",
    )
    label = models.CharField("Подпись на форме", max_length=128)
    field_type = models.CharField(
        "Тип поля", max_length=16, choices=FieldType.choices,
    )
    options = models.JSONField(
        "Варианты выбора", null=True, blank=True,
        help_text='Только для типа «Список». Пример: ["Вариант 1", "Вариант 2"]',
    )
    is_required = models.BooleanField("Обязательное", default=False)
    order_num = models.PositiveSmallIntegerField("Порядок отображения", default=100)
    is_active = models.BooleanField("Активно", default=True)
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)

    class Meta:
        db_table = "field_definition"
        verbose_name = "Пользовательское поле"
        verbose_name_plural = "Конструктор полей"
        ordering = ["order_num"]

    def __str__(self) -> str:
        return f"{self.label} ({self.code})"


# =============================================================================
# 6. АУДИТ
# =============================================================================
class AuditLog(models.Model):
    """Журнал значимых действий пользователей и системы.

    Записи сюда делаются программно из сервисного слоя:
    создание/изменение/удаление сущностей, смена статусов,
    вход/выход пользователей и т. п.
    """
    actor = models.ForeignKey(
        Employee, on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Автор действия",
    )
    action = models.CharField(
        "Действие", max_length=64,
        help_text="create / update / delete / status_change / login / ...",
    )
    entity_type = models.CharField(
        "Тип сущности", max_length=64,
        help_text="request / client / employee / ...",
    )
    entity_id = models.BigIntegerField("ID сущности", null=True, blank=True)
    payload = models.JSONField(
        "Данные", null=True, blank=True,
        help_text="Произвольные детали: до/после, доп. контекст",
    )
    created_at = models.DateTimeField("Дата", auto_now_add=True)

    class Meta:
        db_table = "audit_log"
        verbose_name = "Запись аудита"
        verbose_name_plural = "Аудит-журнал"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["entity_type", "entity_id"]),
            models.Index(fields=["actor", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.action} {self.entity_type}#{self.entity_id}"
