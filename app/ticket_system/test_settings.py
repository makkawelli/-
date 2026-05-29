"""Настройки для запуска автотестов.

Использование:
    pytest                              # настройки берутся из pytest.ini
    python manage.py test --settings=ticket_system.test_settings

Чем отличаются от продовых (settings.py):
- БД переключена на SQLite в памяти — тесты быстрые, не требуют PostgreSQL;
- email-бэкенд — locmem (письма не уходят, копятся в django.core.mail.outbox);
- миграции для приложения core отключены — Django создаёт таблицы напрямую
  по текущему состоянию моделей (см. MIGRATION_MODULES). Это удобно, потому
  что в репозитории миграции пока не зафиксированы и зависят от выбора БД.
"""
from .settings import *  # noqa: F401,F403


# ---------------------------------------------------------------------------
# БД: SQLite в памяти. Быстрее всего и не требует никакой инфраструктуры.
# GinIndex в models.py при таком ENGINE не подключается (условие в models.py).
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}


# ---------------------------------------------------------------------------
# Отключаем миграции — таблицы создаются прямо из моделей.
# Это нужно, потому что миграции, сгенерированные под PostgreSQL, могут
# содержать GIN-индекс, который SQLite не поддерживает.
# ---------------------------------------------------------------------------
class _DisableMigrations:
    def __contains__(self, item: str) -> bool:
        return True

    def __getitem__(self, item: str):
        return None


MIGRATION_MODULES = _DisableMigrations()


# ---------------------------------------------------------------------------
# Email — пишем в память. Тесты затем читают django.core.mail.outbox.
# ---------------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
DEFAULT_FROM_EMAIL = "noreply@ticket-system.test"


# Ускоряем хеширование паролей в тестах — нам не нужна криптостойкость.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]


# Чтобы локальные относительные ссылки в письмах были предсказуемы.
SITE_URL = "http://testserver"

# Кеши и логирование можно оставить дефолтными.
DEBUG = False
