"""Заполнение базовых справочников.

Использование:
    python manage.py seed

Команда идемпотентна — повторный запуск не дублирует записи
(используется get_or_create по уникальному полю code/name).
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from core import models


# Базовый набор данных. Если нужно расширить — добавляйте сюда,
# и команда докатит изменения при следующем запуске.

ROLES = [
    {"code": "admin",    "name": "Администратор"},
    {"code": "manager",  "name": "Менеджер"},
    {"code": "operator", "name": "Оператор"},
    {"code": "executor", "name": "Исполнитель"},
    {"code": "client",   "name": "Клиент"},
]

STATUSES = [
    {"code": "new",         "name": "Новая",          "order_num": 10, "is_terminal": False},
    {"code": "in_progress", "name": "В работе",       "order_num": 20, "is_terminal": False},
    {"code": "on_hold",     "name": "Приостановлена", "order_num": 30, "is_terminal": False},
    {"code": "review",      "name": "На проверке",    "order_num": 40, "is_terminal": False},
    {"code": "done",        "name": "Выполнена",      "order_num": 50, "is_terminal": True},
    {"code": "cancelled",   "name": "Отменена",       "order_num": 60, "is_terminal": True},
]

PRIORITIES = [
    {"code": "low",      "name": "Низкий",      "sla_hours": 72},
    {"code": "medium",   "name": "Средний",     "sla_hours": 24},
    {"code": "high",     "name": "Высокий",     "sla_hours": 8},
    {"code": "critical", "name": "Критический", "sla_hours": 4},
]

SERVICES = [
    {"name": "Консультация",        "default_duration_hours": 2},
    {"name": "Настройка ПО",        "default_duration_hours": 4},
    {"name": "Ремонт оборудования", "default_duration_hours": 8},
    {"name": "Сетевые работы",      "default_duration_hours": 6},
]

TEAMS = [
    "Поддержка 1-й линии",
    "Технические специалисты",
    "Сетевые инженеры",
]


class Command(BaseCommand):
    help = "Заполняет базовые справочники: роли, статусы, приоритеты, услуги, группы."

    @transaction.atomic
    def handle(self, *args, **options):
        self._seed("ролей", models.Role, ROLES, key="code")
        self._seed("статусов", models.Status, STATUSES, key="code")
        self._seed("приоритетов", models.Priority, PRIORITIES, key="code")
        self._seed("услуг", models.Service, SERVICES, key="name")
        self._seed_teams()

        self.stdout.write(self.style.SUCCESS("Готово. Справочники заполнены."))
        self.stdout.write("")
        self.stdout.write("Дальше создайте суперпользователя:")
        self.stdout.write("    python manage.py createsuperuser")

    def _seed(self, kind: str, model, items: list[dict], key: str) -> None:
        created, updated = 0, 0
        for item in items:
            obj, was_created = model.objects.get_or_create(
                **{key: item[key]},
                defaults={k: v for k, v in item.items() if k != key},
            )
            if was_created:
                created += 1
            else:
                # Обновляем атрибуты на случай, если изменились в коде.
                changed = False
                for k, v in item.items():
                    if getattr(obj, k) != v:
                        setattr(obj, k, v)
                        changed = True
                if changed:
                    obj.save()
                    updated += 1
        self.stdout.write(
            f"  {kind}: создано {created}, обновлено {updated}, всего {model.objects.count()}"
        )

    def _seed_teams(self) -> None:
        created = 0
        for name in TEAMS:
            _, was_created = models.Team.objects.get_or_create(name=name)
            if was_created:
                created += 1
        self.stdout.write(
            f"  групп: создано {created}, всего {models.Team.objects.count()}"
        )
