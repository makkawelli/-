"""Контроллеры приложения core (в Django принято называть views).

View — это функция или класс, который принимает HTTP-запрос
и возвращает HTTP-ответ. Обычно ответ — это отрендеренный шаблон.
"""
from django.shortcuts import render


def home(request):
    """Главная страница приложения.

    Пока показывает только приветственный текст, чтобы убедиться,
    что Django + PostgreSQL правильно настроены.
    """
    context = {
        "page_title": "Главная",
    }
    return render(request, "core/home.html", context)
