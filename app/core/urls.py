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

    # Клиенты.
    path("clients/",                  views.client_list,    name="client_list"),
    path("clients/new/",              views.client_create,  name="client_create"),
    path("clients/<int:pk>/",         views.client_detail,  name="client_detail"),
    path("clients/<int:pk>/edit/",    views.client_edit,    name="client_edit"),

    # Отчёты (только для менеджера/админа).
    path("reports/",                  views.reports_index,     name="reports_index"),
    path("reports/by-period/",        views.report_period,     name="report_period"),
    path("reports/by-period.csv",     views.report_period_csv, name="report_period_csv"),
    path("reports/executors/",        views.report_executors_view,     name="report_executors"),
    path("reports/executors.csv",     views.report_executors_csv,      name="report_executors_csv"),
    path("reports/sla/",              views.report_sla_view,   name="report_sla"),
    path("reports/sla.csv",           views.report_sla_csv,    name="report_sla_csv"),
]
