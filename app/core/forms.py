"""Формы Django для приложения core.

Главная особенность RequestForm — динамические поля для low-code-конструктора:
для каждой записи FieldDefinition (is_active=True) автоматически добавляется
поле формы соответствующего типа. Введённые значения сохраняются в JSON-колонку
Request.custom_fields. Это и есть демонстрация ключевого УТП проекта.
"""
from __future__ import annotations

import datetime as dt

from django import forms

from . import models


# =============================================================================
# Заявка
# =============================================================================
class RequestForm(forms.ModelForm):
    """Форма создания/редактирования заявки.

    К стандартным полям модели добавляются динамические low-code-поля,
    описанные в FieldDefinition. Префикс `cf_` нужен, чтобы не пересекаться
    с именами полей модели.
    """

    CUSTOM_PREFIX = "cf_"

    class Meta:
        model = models.Request
        fields = [
            "client", "service", "priority",
            "title", "description",
            "assignee",
        ]
        widgets = {
            "client":      forms.Select(attrs={"class": "form-select"}),
            "service":     forms.Select(attrs={"class": "form-select"}),
            "priority":    forms.Select(attrs={"class": "form-select"}),
            "title":       forms.TextInput(attrs={"class": "form-control",
                                                   "placeholder": "Кратко о проблеме"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 5,
                                                  "placeholder": "Подробности, шаги воспроизведения..."}),
            "assignee":    forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Список исполнителей — сотрудники с ролями executor/manager.
        # Чтобы оператор не назначил заявку «на самого себя» в качестве клиента
        # и чтобы не показывать неактуальных пользователей.
        self.fields["assignee"].queryset = (
            models.Employee.objects
            .filter(is_active=True, role__code__in=["executor", "manager"])
            .order_by("full_name", "username")
        )
        self.fields["assignee"].empty_label = "— не назначен —"
        self.fields["assignee"].required = False

        # Только активные услуги и клиенты.
        self.fields["service"].queryset = models.Service.objects.filter(is_active=True)
        self.fields["client"].queryset = models.Client.objects.order_by("name")

        # Подгружаем активные пользовательские поля и добавляем их в форму.
        self._field_definitions = list(
            models.FieldDefinition.objects
            .filter(is_active=True)
            .order_by("order_num")
        )
        existing = (self.instance.custom_fields if self.instance and self.instance.pk else None) or {}
        for fd in self._field_definitions:
            self.fields[self.CUSTOM_PREFIX + fd.code] = self._build_dynamic_field(fd, existing.get(fd.code))

    @staticmethod
    def _build_dynamic_field(fd: models.FieldDefinition, initial):
        """Сконструировать поле формы по описанию FieldDefinition."""
        common = {
            "label": fd.label,
            "required": fd.is_required and fd.field_type != "checkbox",
            "initial": initial,
        }
        ft = fd.field_type
        if ft == "text":
            return forms.CharField(
                widget=forms.TextInput(attrs={"class": "form-control"}),
                **common,
            )
        if ft == "textarea":
            return forms.CharField(
                widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
                **common,
            )
        if ft == "number":
            return forms.IntegerField(
                widget=forms.NumberInput(attrs={"class": "form-control"}),
                **common,
            )
        if ft == "date":
            # Для DateField initial должен быть date, а из JSON приходит строка.
            if isinstance(initial, str):
                try:
                    common["initial"] = dt.date.fromisoformat(initial)
                except ValueError:
                    common["initial"] = None
            return forms.DateField(
                widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
                **common,
            )
        if ft == "select":
            options = fd.options or []
            choices = [("", "— не выбрано —")] + [(o, o) for o in options]
            return forms.ChoiceField(
                choices=choices,
                widget=forms.Select(attrs={"class": "form-select"}),
                **common,
            )
        if ft == "checkbox":
            return forms.BooleanField(
                label=fd.label,
                required=False,
                initial=bool(initial),
                widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
            )
        # Безопасный fallback на случай, если в БД появится неизвестный тип.
        return forms.CharField(
            widget=forms.TextInput(attrs={"class": "form-control"}),
            **common,
        )

    # -------------------------------------------------------------------------
    # Сборка значений low-code-полей в JSON
    # -------------------------------------------------------------------------
    def get_custom_fields_payload(self) -> dict:
        """Собрать словарь {code: value} из cleaned_data для сохранения в JSONB."""
        payload: dict = {}
        for fd in self._field_definitions:
            key = self.CUSTOM_PREFIX + fd.code
            value = self.cleaned_data.get(key)
            if value in (None, "", False):
                # Не сохраняем «пустые» значения, чтобы JSON оставался компактным.
                # Для checkbox = False тоже не пишем — отсутствие = False.
                continue
            # date в JSON — строкой ISO-формата.
            if isinstance(value, dt.date):
                value = value.isoformat()
            payload[fd.code] = value
        return payload


# =============================================================================
# Комментарий
# =============================================================================
class CommentForm(forms.ModelForm):
    """Форма добавления комментария к заявке."""

    class Meta:
        model = models.Comment
        fields = ["text", "is_internal"]
        widgets = {
            "text": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Напишите комментарий...",
            }),
            "is_internal": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        labels = {
            "text": "",
            "is_internal": "Внутренний (не виден клиенту)",
        }


# =============================================================================
# Фильтры списка заявок
# =============================================================================
# =============================================================================
# Клиенты
# =============================================================================
class ClientForm(forms.ModelForm):
    """Форма создания/редактирования клиента."""

    class Meta:
        model = models.Client
        fields = ["name", "contact_person", "phone", "email"]
        widgets = {
            "name":            forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Например: ООО «Ромашка»",
            }),
            "contact_person":  forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Иванов Иван Иванович",
            }),
            "phone":           forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "+7 (495) 123-45-67",
            }),
            "email":           forms.EmailInput(attrs={
                "class": "form-control",
                "placeholder": "info@example.com",
            }),
        }


class ClientFilterForm(forms.Form):
    """GET-форма поиска клиентов."""
    q = forms.CharField(
        required=False, label="",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Поиск по названию, контактному лицу, телефону, email...",
        }),
    )


# =============================================================================
# Фильтры списка заявок
# =============================================================================
class RequestFilterForm(forms.Form):
    """GET-форма фильтрации списка заявок.

    Используется во views.request_list — генерирует UI и кладёт значения
    в queryset. Все поля необязательны.
    """
    q = forms.CharField(
        required=False, label="",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Поиск по номеру, теме, описанию...",
        }),
    )
    status = forms.ModelChoiceField(
        required=False, label="Статус",
        queryset=models.Status.objects.order_by("order_num"),
        empty_label="Все статусы",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    priority = forms.ModelChoiceField(
        required=False, label="Приоритет",
        queryset=models.Priority.objects.order_by("sla_hours"),
        empty_label="Любой приоритет",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    assignee = forms.ModelChoiceField(
        required=False, label="Исполнитель",
        queryset=models.Employee.objects.filter(is_active=True).order_by("full_name", "username"),
        empty_label="Любой исполнитель",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    only_open = forms.BooleanField(
        required=False, label="Только открытые",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    overdue = forms.BooleanField(
        required=False, label="Только просроченные",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    date_from = forms.DateField(
        required=False, label="Создана с",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    date_to = forms.DateField(
        required=False, label="Создана по",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
