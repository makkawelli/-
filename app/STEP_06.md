# Шаг 6. Автоматические тесты (pytest + pytest-django)

К моменту начала этого шага у нас уже работает Шаг 5: полный UI заявок,
отчёты, клиенты, уведомления. Теперь добавляем **автотесты**, которые
гарантируют, что бизнес-логика работает корректно: модели, RBAC, FSM,
сервисы, уведомления, отчёты.

Это самый ценный для защиты ВКР шаг: научный руководитель и комиссия
любят, когда есть хоть какие-то автотесты.

---

## Что делаем

1. ставим dev-зависимости (`pytest`, `pytest-django`);
2. создаём отдельные настройки для тестов (`ticket_system/test_settings.py`)
   — SQLite в памяти, чтобы не зависеть от PostgreSQL;
3. создаём фикстуры в `core/tests/conftest.py` (роли, статусы, пользователи
   всех ролей, клиент, фабрика заявок);
4. пишем 5 файлов тестов (~85 кейсов):
   - `test_models.py` — генератор номеров, custom_fields, terminal-флаги;
   - `test_permissions.py` — RBAC-матрица и FSM-карта переходов;
   - `test_services.py` — create_request / transition_request / add_comment;
   - `test_notifications.py` — 4 email-события;
   - `test_reports.py` — отчёты by_period / executors / SLA / dashboard;
5. запускаем `pytest`, убеждаемся, что **все тесты зелёные**.

---

## Что нового в проекте

```
app/
├── pytest.ini                          ← конфиг pytest (NEW)
├── requirements-dev.txt                ← dev-зависимости (NEW)
├── ticket_system/
│   ├── settings.py                     ← без изменений (PostgreSQL остаётся)
│   └── test_settings.py                ← SQLite + locmem email (NEW)
└── core/
    ├── models.py                       ← GIN-индекс теперь условный (UPDATED)
    └── tests/                          ← (NEW)
        ├── __init__.py
        ├── conftest.py                 ← фикстуры
        ├── test_models.py
        ├── test_permissions.py
        ├── test_services.py
        ├── test_notifications.py
        └── test_reports.py
```

---

## Шаг 6.1. Установка dev-зависимостей

В корне проекта (там же, где `manage.py`):

```powershell
cd C:\path\to\diploma\app
.\venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

Эта команда установит `pytest` и `pytest-django` поверх уже стоящих
зависимостей (`requirements.txt` подключён через `-r`).

Проверка установки:

```powershell
pytest --version
```

Должно вывести что-то вроде `pytest 8.3.4`.

---

## Шаг 6.2. Запуск тестов

### Вся пачка разом

```powershell
pytest
```

Ожидаемый итог:

```
============================= test session starts =============================
platform win32 -- Python 3.x.x, pytest-8.3.4, pluggy-x.x.x
django: settings: ticket_system.test_settings (from ini)
rootdir: C:\path\to\diploma\app
plugins: django-4.9.0
collected 80+ items

core/tests/test_models.py ............                               [ 14%]
core/tests/test_permissions.py .........................             [ 45%]
core/tests/test_services.py .................                        [ 65%]
core/tests/test_notifications.py ..........                          [ 78%]
core/tests/test_reports.py ..................                        [100%]

============================= 80+ passed in 4.5s =============================
```

### Только конкретный файл

```powershell
pytest core/tests/test_permissions.py
```

### Только один класс / тест

```powershell
pytest core/tests/test_permissions.py::TestCanTransition
pytest core/tests/test_services.py::TestTransitionRequest::test_sets_closed_at_on_terminal
```

### Подробный вывод (видеть имена всех тестов)

```powershell
pytest -v
```

### С coverage (по желанию)

```powershell
pip install pytest-cov
pytest --cov=core --cov-report=term-missing
```

---

## Шаг 6.3. Что покрыто

### `test_models.py` — модели и генератор номеров (~10 кейсов)

- `TestRequestNumber` — формат `REQ-YYYY-NNNNNN`, инкремент, 6 цифр с
  ведущими нулями.
- `TestRequestDefaults` — `custom_fields={}` по умолчанию; due_date
  считается из priority.sla_hours.
- `TestStatusTerminalFlag` — `done` и `cancelled` терминальные;
  остальные нет.
- `TestStrRepresentations` — `__str__` для админки.

### `test_permissions.py` — RBAC и FSM (~25 кейсов)

- `TestCanCreateRequest` — кто может создавать заявки.
- `TestCanEditRequest` — staff может, executor нет.
- `TestCanViewRequest` — executor видит только свои.
- `TestReportsAndClientsAccess` — отчёты только для admin/manager;
  клиенты видны всем сотрудникам, но executor не редактирует.
- `TestVisibleRequestsQs` — фильтрация списка заявок.
- `TestStateMachineMap` — полная карта `ALLOWED_TRANSITIONS` (фиксируем
  все 6 узлов FSM).
- `TestCanTransition` — operator не может закрыть в `done`,
  executor — только свои заявки.

### `test_services.py` — сервисный слой (~17 кейсов)

- `TestCreateRequest` — пишет StatusHistory + AuditLog, ставит due_date,
  сохраняет custom_fields.
- `TestTransitionRequest` — пишет StatusHistory(from→to) + AuditLog,
  закрывает заявку (closed_at) при переходе в done/cancelled,
  сбрасывает closed_at при возврате в открытый статус.
- `TestAddComment` — комментарий + AuditLog, флаг is_internal.
- `TestCalculateDueDate` — отдельная утилита SLA-расчёта.

### `test_notifications.py` — email (~10 кейсов)

- `TestNotifyRequestCreated` — клиенту при создании; молчит, если у
  клиента нет email.
- `TestNotifyRequestAssigned` — исполнителю; молчит без assignee.
- `TestNotifyStatusChanged` — клиенту, кроме перехода в new.
- `TestNotifyCommentAdded` — публичный коммент → клиенту,
  внутренний — нет.
- `TestServicesFireNotifications` — интеграция с
  `transaction.on_commit`: создание заявки реально шлёт письма после
  коммита (используется `@pytest.mark.django_db(transaction=True)`).

### `test_reports.py` — отчётность (~18 кейсов)

- `TestParseDate / TestDefaultPeriod` — утилиты.
- `TestReportByPeriod` — счётчики created/closed по дням, структура
  chart-данных для Chart.js.
- `TestReportExecutors` — total/open/done/overdue; в выборке только
  исполнители и менеджеры (оператор отсутствует).
- `TestReportSla` — «в срок» / «просрочено» / открытые с истёкшим
  due_date / общий процент SLA.
- `TestLiveDashboardMetrics` — open_total (только не-терминальные),
  overdue (только открытые), unassigned, разбивка by_status.

---

## Шаг 6.4. Архитектурные заметки (для ВКР)

В дипломе можно отдельным абзацем упомянуть:

1. **Тесты используют SQLite в памяти**, чтобы не зависеть от
   PostgreSQL. Для этого создан `test_settings.py` с переопределённой
   конфигурацией БД и отключёнными миграциями (`MIGRATION_MODULES`).
   GIN-индекс по JSONB-полю `custom_fields` подключается в `models.py`
   условно — только при PostgreSQL, что позволяет одной кодовой базой
   обслуживать и продовый прогон под Postgres, и быстрые тесты под
   SQLite.

2. **Покрыты все слои**: модели (валидация, дефолты), доменные правила
   (RBAC, FSM), сервисный слой (бизнес-операции с побочными эффектами:
   StatusHistory, AuditLog, email), и вычислительный слой (отчёты).

3. **Email-уведомления** проверяются и в юнит-режиме (прямой вызов
   `notify_*`), и в интеграционном (через сервисы и
   `transaction.on_commit` с реальным коммитом транзакции).

4. **Использование pytest** вместо встроенного `django.test.TestCase`
   — современная индустриальная практика: лаконичный синтаксис,
   мощная система фикстур, параметризация.

---

## Чек-лист для отчёта по шагу 6

- [ ] `pip install -r requirements-dev.txt` прошёл без ошибок;
- [ ] `pytest --version` показывает 8.3.x;
- [ ] `pytest` — все тесты зелёные;
- [ ] скриншот сделан: терминал PowerShell с зелёным `XX passed`;
- [ ] (опционально) `pytest --cov=core` — снять % покрытия для ВКР.

## Что прислать в ответ

1. Скриншот с зелёным выводом `pytest`;
2. Сообщение «Шаг 6 готов» — переходим к шагу B (графики SLA + drill-down).

---

## Возможные проблемы и их решения

### `ModuleNotFoundError: No module named 'pytest'`
Не установлен pytest. Запусти:
```powershell
pip install -r requirements-dev.txt
```

### `django.core.exceptions.ImproperlyConfigured: Requested setting ...`
В `pytest.ini` неправильно прописан `DJANGO_SETTINGS_MODULE`, или его
не подхватывает. Убедись, что pytest запускается **из папки `app/`**
(там лежит `pytest.ini`).

### `OperationalError: no such table: ...`
Тесты пытались работать на SQLite, но миграции не применились. Убедись,
что в `test_settings.py` есть блок `MIGRATION_MODULES = _DisableMigrations()`
— без него SQLite попытается применить PG-специфичные миграции и упадёт.

### Тест на email падает: `len(mailoutbox) == 0`
Скорее всего письма не отправились, потому что `transaction.on_commit`
не сработал. Это нормально: для интеграционных тестов с email нужен
декоратор `@pytest.mark.django_db(transaction=True)`. У нас он уже
проставлен в `TestServicesFireNotifications`.

### Тест отчётов падает на «`avg_hours` == None»
SQLite по-разному считает разности `DateTimeField`, чем PostgreSQL.
Это известное место: в данной реализации проверка `avg_hours`
сознательно НЕ делается в тестах, чтобы не привязываться к диалекту БД.
В живом приложении (PG) поле считается корректно.
