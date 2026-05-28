#!/usr/bin/env python
"""Django CLI-утилита.

Позволяет запускать команды управления проектом:
    python manage.py runserver           # запуск локального веб-сервера
    python manage.py migrate             # применить миграции БД
    python manage.py makemigrations      # создать миграции из моделей
    python manage.py createsuperuser     # создать администратора
    python manage.py shell               # интерактивная Python-оболочка с подключённым ORM
"""
import os
import sys


def main() -> None:
    # Указываем Django, какой модуль настроек использовать.
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ticket_system.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "Не удалось импортировать Django. Убедитесь, что:\n"
            "  1) активировано виртуальное окружение (venv);\n"
            "  2) выполнена команда `pip install -r requirements.txt`."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
