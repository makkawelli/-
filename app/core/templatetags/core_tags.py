"""Кастомные шаблонные теги и фильтры для core.

Используются для красивого отображения в шаблонах:
- цвета бейджей статусов / приоритетов;
- иконки переходов статусов.
"""
from django import template

register = template.Library()


# =============================================================================
# Цвета Bootstrap (классы btn-*, bg-*) для статусов и приоритетов.
# =============================================================================
STATUS_COLORS = {
    "new":         "secondary",
    "in_progress": "primary",
    "on_hold":     "warning",
    "review":      "info",
    "done":        "success",
    "cancelled":   "dark",
}

PRIORITY_COLORS = {
    "low":      "light",
    "medium":   "secondary",
    "high":     "warning",
    "critical": "danger",
}

STATUS_ICONS = {
    "new":         "bi-circle",
    "in_progress": "bi-play-circle",
    "on_hold":     "bi-pause-circle",
    "review":      "bi-eye",
    "done":        "bi-check-circle",
    "cancelled":   "bi-x-circle",
}


@register.filter
def status_color(status_obj):
    """Класс Bootstrap-цвета для статуса. Использование: {{ req.status|status_color }}"""
    if not status_obj:
        return "secondary"
    return STATUS_COLORS.get(status_obj.code, "secondary")


@register.filter
def status_icon(status_obj):
    """CSS-класс иконки Bootstrap Icons для статуса."""
    if not status_obj:
        return "bi-circle"
    return STATUS_ICONS.get(status_obj.code, "bi-circle")


@register.filter
def priority_color(priority_obj):
    """Класс Bootstrap-цвета для приоритета."""
    if not priority_obj:
        return "secondary"
    return PRIORITY_COLORS.get(priority_obj.code, "secondary")
