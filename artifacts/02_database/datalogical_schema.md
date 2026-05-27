# Даталогическая модель БД

**СУБД:** PostgreSQL 15+  
**Кодировка:** UTF-8  
**Уровень нормализации:** 3НФ  
**Особенность:** в таблице `request` присутствует JSONB-колонка `custom_fields` для хранения значений пользовательских полей, описания которых лежат в `field_definition`. Это сознательная денормализация ради реализации low-code-конструктора без миграций БД.

Сокращения: PK — первичный ключ, FK — внешний ключ, UQ — уникальный, NN — NOT NULL, IDX — индекс.

---

## 1. Справочники

### 1.1. `role` — роли пользователей

| Поле | Тип | Огранич. | Назначение |
|---|---|---|---|
| `id` | `SMALLSERIAL` | PK | Идентификатор |
| `code` | `VARCHAR(32)` | NN, UQ | Машинный код: `admin`, `manager`, `operator`, `executor`, `client` |
| `name` | `VARCHAR(64)` | NN | Отображаемое название |

### 1.2. `service` — каталог услуг

| Поле | Тип | Огранич. | Назначение |
|---|---|---|---|
| `id` | `SERIAL` | PK | |
| `name` | `VARCHAR(128)` | NN | Название услуги |
| `description` | `TEXT` | | Подробное описание |
| `default_duration_hours` | `INTEGER` | | Плановое время выполнения, часов |
| `is_active` | `BOOLEAN` | NN, DEFAULT TRUE | Доступна для выбора |

### 1.3. `status` — статусы заявки

| Поле | Тип | Огранич. | Назначение |
|---|---|---|---|
| `id` | `SMALLSERIAL` | PK | |
| `code` | `VARCHAR(32)` | NN, UQ | `new`, `in_progress`, `on_hold`, `review`, `done`, `cancelled` |
| `name` | `VARCHAR(64)` | NN | Отображаемое название |
| `order_num` | `SMALLINT` | NN | Порядок отображения |
| `is_terminal` | `BOOLEAN` | NN, DEFAULT FALSE | Признак финального статуса |

### 1.4. `priority` — приоритеты

| Поле | Тип | Огранич. | Назначение |
|---|---|---|---|
| `id` | `SMALLSERIAL` | PK | |
| `code` | `VARCHAR(16)` | NN, UQ | `low`, `medium`, `high`, `critical` |
| `name` | `VARCHAR(32)` | NN | |
| `sla_hours` | `INTEGER` | NN | Норматив SLA в часах |

### 1.5. `team` — группы исполнителей

| Поле | Тип | Огранич. | Назначение |
|---|---|---|---|
| `id` | `SERIAL` | PK | |
| `name` | `VARCHAR(128)` | NN, UQ | Название группы |

---

## 2. Пользователи и клиенты

### 2.1. `employee` — сотрудники

| Поле | Тип | Огранич. | Назначение |
|---|---|---|---|
| `id` | `SERIAL` | PK | |
| `full_name` | `VARCHAR(255)` | NN | ФИО |
| `position` | `VARCHAR(128)` | | Должность |
| `login` | `VARCHAR(64)` | NN, UQ | Логин |
| `email` | `VARCHAR(255)` | NN, UQ | E-mail |
| `password_hash` | `VARCHAR(255)` | NN | Хеш пароля (Argon2) |
| `role_id` | `SMALLINT` | NN, FK→`role` | Роль |
| `is_active` | `BOOLEAN` | NN, DEFAULT TRUE | Активен |
| `created_at` | `TIMESTAMPTZ` | NN, DEFAULT NOW() | |

**Индексы:** `IDX(login)`, `IDX(email)`, `IDX(role_id)`.

### 2.2. `employee_team` — связь «сотрудник ↔ группа» (M:N)

| Поле | Тип | Огранич. |
|---|---|---|
| `employee_id` | `INTEGER` | NN, FK→`employee` |
| `team_id` | `INTEGER` | NN, FK→`team` |

**PK:** `(employee_id, team_id)`.

### 2.3. `client` — клиенты (контрагенты)

| Поле | Тип | Огранич. | Назначение |
|---|---|---|---|
| `id` | `SERIAL` | PK | |
| `name` | `VARCHAR(255)` | NN | Наименование организации/ФИО |
| `contact_person` | `VARCHAR(255)` | | Контактное лицо |
| `phone` | `VARCHAR(32)` | | Телефон |
| `email` | `VARCHAR(255)` | | E-mail |
| `created_at` | `TIMESTAMPTZ` | NN, DEFAULT NOW() | |

**Индексы:** `IDX(phone)`, `IDX(email)`, `GIN(name gin_trgm_ops)` — для нечёткого поиска по названию.

---

## 3. Ядро системы

### 3.1. `request` — заявки

| Поле | Тип | Огранич. | Назначение |
|---|---|---|---|
| `id` | `BIGSERIAL` | PK | |
| `number` | `VARCHAR(32)` | NN, UQ | Сквозной номер вида `REQ-2026-000123` |
| `client_id` | `INTEGER` | NN, FK→`client` | |
| `service_id` | `INTEGER` | NN, FK→`service` | |
| `status_id` | `SMALLINT` | NN, FK→`status` | Текущий статус |
| `priority_id` | `SMALLINT` | NN, FK→`priority` | |
| `assignee_id` | `INTEGER` | FK→`employee` | Исполнитель (NULL — не назначен) |
| `created_by` | `INTEGER` | NN, FK→`employee` | Автор регистрации |
| `title` | `VARCHAR(255)` | NN | Краткое описание |
| `description` | `TEXT` | | Подробное описание |
| `due_date` | `TIMESTAMPTZ` | | Срок (вычисляется по SLA приоритета) |
| `closed_at` | `TIMESTAMPTZ` | | Дата закрытия |
| `custom_fields` | `JSONB` | NN, DEFAULT `'{}'` | Значения low-code-полей |
| `created_at` | `TIMESTAMPTZ` | NN, DEFAULT NOW() | |
| `updated_at` | `TIMESTAMPTZ` | NN, DEFAULT NOW() | Триггер |

**Индексы:**
- `IDX(client_id)`, `IDX(assignee_id)`, `IDX(status_id)`, `IDX(priority_id)`, `IDX(service_id)`
- `IDX(created_at DESC)` — для лент и пагинации
- `GIN(custom_fields)` — для фильтрации по кастомным полям
- `GIN(to_tsvector('russian', title || ' ' || description))` — полнотекстовый поиск

**Бизнес-правило:** при `status.is_terminal = TRUE` устанавливается `closed_at = NOW()` (триггер).

### 3.2. `comment` — комментарии к заявке

| Поле | Тип | Огранич. | Назначение |
|---|---|---|---|
| `id` | `BIGSERIAL` | PK | |
| `request_id` | `BIGINT` | NN, FK→`request` ON DELETE CASCADE | |
| `author_id` | `INTEGER` | NN, FK→`employee` | |
| `text` | `TEXT` | NN | |
| `is_internal` | `BOOLEAN` | NN, DEFAULT FALSE | Только для сотрудников (не виден клиенту) |
| `created_at` | `TIMESTAMPTZ` | NN, DEFAULT NOW() | |

**Индексы:** `IDX(request_id, created_at DESC)`.

### 3.3. `attachment` — вложения

| Поле | Тип | Огранич. |
|---|---|---|
| `id` | `BIGSERIAL` | PK |
| `request_id` | `BIGINT` | NN, FK→`request` ON DELETE CASCADE |
| `file_name` | `VARCHAR(255)` | NN |
| `file_path` | `VARCHAR(512)` | NN |
| `file_size` | `BIGINT` | NN |
| `mime_type` | `VARCHAR(128)` | |
| `uploaded_by` | `INTEGER` | NN, FK→`employee` |
| `uploaded_at` | `TIMESTAMPTZ` | NN, DEFAULT NOW() |

**Индексы:** `IDX(request_id)`.

### 3.4. `status_history` — история переходов статуса

| Поле | Тип | Огранич. |
|---|---|---|
| `id` | `BIGSERIAL` | PK |
| `request_id` | `BIGINT` | NN, FK→`request` ON DELETE CASCADE |
| `status_from_id` | `SMALLINT` | FK→`status` (NULL для регистрации) |
| `status_to_id` | `SMALLINT` | NN, FK→`status` |
| `changed_by` | `INTEGER` | NN, FK→`employee` |
| `comment` | `TEXT` | |
| `changed_at` | `TIMESTAMPTZ` | NN, DEFAULT NOW() |

**Индексы:** `IDX(request_id, changed_at)`.

---

## 4. Маршрутизация и low-code

### 4.1. `routing_rule` — правила автоматической маршрутизации

| Поле | Тип | Огранич. |
|---|---|---|
| `id` | `SERIAL` | PK |
| `service_id` | `INTEGER` | NN, FK→`service` |
| `team_id` | `INTEGER` | NN, FK→`team` |
| `priority_order` | `SMALLINT` | NN, DEFAULT 100 (порядок применения) |
| `is_active` | `BOOLEAN` | NN, DEFAULT TRUE |

### 4.2. `field_definition` — описание пользовательских полей

| Поле | Тип | Огранич. | Назначение |
|---|---|---|---|
| `id` | `SERIAL` | PK | |
| `code` | `VARCHAR(64)` | NN, UQ | Ключ внутри JSONB `custom_fields` |
| `label` | `VARCHAR(128)` | NN | Подпись на форме |
| `field_type` | `VARCHAR(16)` | NN | `text`/`number`/`date`/`select`/`checkbox`/`textarea` |
| `options` | `JSONB` | | Список вариантов для `select` |
| `is_required` | `BOOLEAN` | NN, DEFAULT FALSE | |
| `order_num` | `SMALLINT` | NN, DEFAULT 100 | Порядок на форме |
| `is_active` | `BOOLEAN` | NN, DEFAULT TRUE | |
| `created_at` | `TIMESTAMPTZ` | NN, DEFAULT NOW() | |

**Пример работы:**
1. Администратор через UI создаёт `field_definition`: `code='vehicle_vin'`, `label='VIN автомобиля'`, `field_type='text'`, `is_required=true`.
2. Frontend, рендеря карточку заявки, читает все активные `field_definition` и динамически добавляет поля на форму.
3. При сохранении значение уходит в `request.custom_fields` как `{"vehicle_vin": "WBA..."}`.
4. Поиск/фильтрация по этому полю работает через GIN-индекс на `custom_fields`.

---

## 5. Аудит

### 5.1. `audit_log` — журнал значимых действий

| Поле | Тип | Огранич. |
|---|---|---|
| `id` | `BIGSERIAL` | PK |
| `actor_id` | `INTEGER` | FK→`employee` (NULL для системных событий) |
| `action` | `VARCHAR(64)` | NN — `create`/`update`/`delete`/`status_change`/`assign`/`login` |
| `entity_type` | `VARCHAR(64)` | NN — `request`/`client`/`employee`/... |
| `entity_id` | `BIGINT` | |
| `payload` | `JSONB` | Поля до/после |
| `created_at` | `TIMESTAMPTZ` | NN, DEFAULT NOW() |

**Индексы:** `IDX(entity_type, entity_id)`, `IDX(actor_id, created_at DESC)`.

---

## 6. Соответствие функциональным требованиям из НИР

| ФТ | Где реализовано |
|---|---|
| ФТ-1 «Управление профилями клиентов» | `client` |
| ФТ-2.1 «Регистрация заявки с указанием клиента, услуги, описания, приоритета» | `request` + FK |
| ФТ-2.2 «Уникальный сквозной номер, дата, автор» | `request.number` (UQ), `created_at`, `created_by` |
| ФТ-2.3 «Назначение исполнителя/группы» | `request.assignee_id`, `routing_rule` |
| ФТ-2.4 «Жизненный цикл с фиксацией истории» | `status` + `status_history` |
| ФТ-2.5 «Комментарии и вложения» | `comment`, `attachment` |
| ФТ-2.6 «Приостановка/возобновление/отмена» | `status` + статусы `on_hold`, `cancelled` |
| ФТ-3.1 «Справочники» | `service`, `status`, `priority`, `team` |
| ФТ-3.2 «Учётные записи и роли» | `employee`, `role` |
| ФТ-3.3 «Правила маршрутизации» | `routing_rule` |
| ФТ-4.1 «Стандартные отчёты» | SQL-выборки из `request` + индексы |
| ФТ-4.3 «Аудит-журнал» | `audit_log` |
| Low-code (УТП из презентации) | `field_definition` + `request.custom_fields` JSONB |

---

## 7. Диаграмма переходов статусов (FSM)

```
       ┌──────────┐
       │   new    │ ◄── регистрация
       └────┬─────┘
            │  назначить исполнителя
            ▼
   ┌─────────────────┐    ┌─────────────┐
   │   in_progress   │ ─► │   on_hold   │ (приостановка)
   └────────┬────────┘    └──────┬──────┘
            │                    │ возобновить
            │ ◄──────────────────┘
            │
            │ исполнитель: «выполнено»
            ▼
   ┌─────────────────┐
   │     review      │
   └────────┬────────┘
            │ менеджер/клиент: «принято»
            ▼
   ┌─────────────────┐         ┌─────────────┐
   │      done       │         │  cancelled  │  (отмена с любого
   └─────────────────┘         └─────────────┘   нефинального)
       (terminal)                  (terminal)
```

Эти переходы валидируются на бэкенде в сервисном слое (state machine), а исторические записи фиксируются в `status_history`.
