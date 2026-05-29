"""Регистрация моделей в Django Admin.

Админка Django — это готовый CRUD-интерфейс. Достаточно зарегистрировать
модель, и для неё появятся страницы списка, создания, редактирования, удаления.

Для каждой модели мы донастраиваем:
    list_display    — какие колонки показывать в списке
    list_filter     — фильтры справа
    search_fields   — поля для поиска
    list_per_page   — количество строк на страницу
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from . import models


# =============================================================================
# Справочники
# =============================================================================
@admin.register(models.Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "name")
    search_fields = ("code", "name")


@admin.register(models.Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "default_duration_hours", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(models.Status)
class StatusAdmin(admin.ModelAdmin):
    list_display = ("order_num", "code", "name", "is_terminal")
    list_filter = ("is_terminal",)
    ordering = ("order_num",)


@admin.register(models.Priority)
class PriorityAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "sla_hours")


@admin.register(models.Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


# =============================================================================
# Сотрудник = пользователь
# =============================================================================
@admin.register(models.Employee)
class EmployeeAdmin(UserAdmin):
    """Админка сотрудника: расширяем стандартную UserAdmin своими полями."""

    # В список добавляем full_name, position, role.
    # is_staff и is_superuser — технические поля Django, не показываем в списке,
    # чтобы не путать с нашей ролевой моделью (role).
    list_display = ("username", "full_name", "email", "position", "role", "is_active")
    list_filter = ("role", "is_active", "teams")
    search_fields = ("username", "full_name", "email")

    # Добавляем секцию «Профиль сотрудника» в форму редактирования.
    # fieldsets от UserAdmin содержит все стандартные секции; мы их не трогаем,
    # а добавляем свою через add_fieldsets/fieldsets.
    fieldsets = UserAdmin.fieldsets + (
        ("Профиль сотрудника", {
            "fields": ("full_name", "position", "role", "teams"),
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Профиль сотрудника", {
            "fields": ("full_name", "position", "role"),
        }),
    )
    filter_horizontal = ("teams", "groups", "user_permissions")


# =============================================================================
# Клиенты
# =============================================================================
@admin.register(models.Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "contact_person", "phone", "email", "created_at")
    search_fields = ("name", "contact_person", "phone", "email")
    list_per_page = 50


# =============================================================================
# Заявки
# =============================================================================
class CommentInline(admin.TabularInline):
    """Комментарии редактируются прямо на странице заявки."""
    model = models.Comment
    extra = 0
    readonly_fields = ("created_at",)
    fields = ("author", "text", "is_internal", "created_at")


class StatusHistoryInline(admin.TabularInline):
    """История статусов — только просмотр."""
    model = models.StatusHistory
    extra = 0
    can_delete = False
    readonly_fields = ("status_from", "status_to", "changed_by", "comment", "changed_at")

    def has_add_permission(self, request, obj=None):
        # Историю нельзя создавать руками — только через сервисный слой.
        return False


class AttachmentInline(admin.TabularInline):
    model = models.Attachment
    extra = 0
    readonly_fields = ("file_size", "mime_type", "uploaded_by", "uploaded_at")


@admin.register(models.Request)
class RequestAdmin(admin.ModelAdmin):
    list_display = (
        "number", "title", "client", "service",
        "status", "priority", "assignee", "created_at",
    )
    list_filter = ("status", "priority", "service", "assignee")
    search_fields = ("number", "title", "description", "client__name")
    raw_id_fields = ("client", "assignee", "created_by")
    readonly_fields = ("created_at", "updated_at", "closed_at")
    inlines = [CommentInline, AttachmentInline, StatusHistoryInline]
    list_per_page = 50

    fieldsets = (
        (None, {
            "fields": ("number", "title", "description"),
        }),
        ("Связи", {
            "fields": ("client", "service", "priority", "status", "assignee", "created_by"),
        }),
        ("Сроки", {
            "fields": ("due_date", "closed_at"),
        }),
        ("Дополнительно", {
            "fields": ("custom_fields",),
            "classes": ("collapse",),
        }),
        ("Системные поля", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )


# =============================================================================
# Маршрутизация и low-code
# =============================================================================
@admin.register(models.RoutingRule)
class RoutingRuleAdmin(admin.ModelAdmin):
    list_display = ("service", "team", "priority_order", "is_active")
    list_filter = ("is_active", "service", "team")


@admin.register(models.FieldDefinition)
class FieldDefinitionAdmin(admin.ModelAdmin):
    list_display = ("order_num", "label", "code", "field_type", "is_required", "is_active")
    list_filter = ("field_type", "is_active", "is_required")
    search_fields = ("code", "label")
    ordering = ("order_num",)


# =============================================================================
# Аудит-журнал (только просмотр)
# =============================================================================
@admin.register(models.AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "entity_type", "entity_id")
    list_filter = ("action", "entity_type")
    search_fields = ("entity_type", "entity_id", "action")
    readonly_fields = ("actor", "action", "entity_type", "entity_id", "payload", "created_at")
    list_per_page = 100

    def has_add_permission(self, request):
        return False  # записи делаются только программно

    def has_change_permission(self, request, obj=None):
        return False  # только просмотр


# =============================================================================
# Настройка заголовков админки
# =============================================================================
admin.site.site_header = "ИС «Учёт заявок» — администрирование"
admin.site.site_title = "Админка"
admin.site.index_title = "Управление системой"
