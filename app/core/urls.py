"""URL-маршруты приложения core.

Подключаются в ticket_system/urls.py через include('core.urls').
"""
from django.urls import path

from . import views


# app_name позволяет ссылаться на маршруты как "core:home" в шаблонах.
app_name = "core"

urlpatterns = [
    # Главная (дашборд).
    path("", views.home, name="home"),

    # Заявки.
    path("requests/",                                views.request_list,        name="request_list"),
    path("requests/new/",                            views.request_create,      name="request_create"),
    path("requests/<str:number>/",                   views.request_detail,      name="request_detail"),
    path("requests/<str:number>/edit/",              views.request_edit,        name="request_edit"),
    path("requests/<str:number>/transition/<str:to_status>/",
                                                     views.request_transition,  name="request_transition"),
    path("requests/<str:number>/comment/",           views.request_add_comment, name="request_add_comment"),
]
