"""Настройки Django-проекта.

Документация: https://docs.djangoproject.com/en/5.1/topics/settings/
"""
from pathlib import Path

from dotenv import load_dotenv
import os

# Корневая папка проекта (на уровне выше этого файла).
BASE_DIR = Path(__file__).resolve().parent.parent

# Подгружаем переменные из файла .env, если он существует.
# Это позволяет хранить секреты (SECRET_KEY, пароль БД) вне репозитория.
load_dotenv(BASE_DIR / ".env")


def env(key: str, default: str | None = None) -> str:
    """Прочитать переменную окружения; если не задана — вернуть значение по умолчанию."""
    value = os.environ.get(key, default)
    if value is None:
        raise RuntimeError(f"Переменная окружения {key} не задана. Заполните .env по образцу .env.example.")
    return value


# ============================================================================
# БЕЗОПАСНОСТЬ
# ============================================================================
SECRET_KEY = env("DJANGO_SECRET_KEY", "insecure-default-key-change-me")
DEBUG = env("DJANGO_DEBUG", "True").lower() in ("1", "true", "yes")
ALLOWED_HOSTS = [h.strip() for h in env("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if h.strip()]


# ============================================================================
# ПРИЛОЖЕНИЯ
# ============================================================================
INSTALLED_APPS = [
    # Встроенные приложения Django.
    "django.contrib.admin",          # административный интерфейс
    "django.contrib.auth",           # аутентификация и пользователи
    "django.contrib.contenttypes",   # generic-отношения (нужен для admin/auth)
    "django.contrib.sessions",       # сессии (для входа/выхода)
    "django.contrib.messages",       # flash-сообщения для пользователя
    "django.contrib.staticfiles",    # обслуживание CSS/JS/изображений в DEBUG-режиме

    # Расширения PostgreSQL: GIN-индексы, ArrayField, и т. п.
    "django.contrib.postgres",

    # Наши приложения.
    "core.apps.CoreConfig",          # бизнес-логика ИС учёта заявок
]


# Используем кастомную модель пользователя core.Employee
# вместо стандартной django.contrib.auth.User.
# Это нужно ОДИН РАЗ задать перед самой первой миграцией.
AUTH_USER_MODEL = "core.Employee"


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "ticket_system.urls"


# ============================================================================
# ШАБЛОНЫ
# ============================================================================
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # Папка с глобальными шаблонами (например, base.html).
        "DIRS": [BASE_DIR / "templates"],
        # Также Django ищет шаблоны в каждой <app>/templates/.
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "ticket_system.wsgi.application"


# ============================================================================
# БАЗА ДАННЫХ
# ============================================================================
# Используем PostgreSQL через современный драйвер psycopg (v3).
# Реквизиты задаются в файле .env.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME":     env("POSTGRES_DB",       "ticket_system"),
        "USER":     env("POSTGRES_USER",     "postgres"),
        "PASSWORD": env("POSTGRES_PASSWORD", "postgres"),
        "HOST":     env("POSTGRES_HOST",     "127.0.0.1"),
        "PORT":     env("POSTGRES_PORT",     "5432"),
    }
}


# ============================================================================
# АУТЕНТИФИКАЦИЯ
# ============================================================================
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Куда отправляется пользователь после успешного входа/выхода.
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"


# ============================================================================
# ИНТЕРНАЦИОНАЛИЗАЦИЯ
# ============================================================================
LANGUAGE_CODE = "ru-RU"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True


# ============================================================================
# СТАТИКА И ЗАГРУЖАЕМЫЕ ФАЙЛЫ
# ============================================================================
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"


# ============================================================================
# EMAIL (для разработки — пишем письма в консоль)
# ============================================================================
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "noreply@ticket-system.local"


# ============================================================================
# ПРОЧЕЕ
# ============================================================================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
