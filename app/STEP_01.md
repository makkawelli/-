# Шаг 1. Модели БД и миграции

Этот файл — короткая инструкция, что нужно выполнить **после `git pull`**.
Большая инструкция по установке Python и PostgreSQL — в `README.md`.

## Что появилось в коде

- **`core/models.py`** — 14 моделей по проектной схеме:
  Role, Service, Status, Priority, Team, **Employee** (кастомная модель пользователя),
  Client, Request (заявка), Comment, Attachment, StatusHistory, RoutingRule,
  FieldDefinition, AuditLog.
- **`core/admin.py`** — все модели зарегистрированы в Django Admin
  с поиском, фильтрами, inline-редактированием комментариев и истории.
- **`core/management/commands/seed.py`** — команда `python manage.py seed`
  для заполнения базовых справочников (роли, статусы, приоритеты, услуги, группы).
- **`ticket_system/settings.py`** — добавлена строка `AUTH_USER_MODEL = "core.Employee"`.

## Важно: придётся пересоздать БД

Поскольку мы переключились на кастомную модель пользователя
(`Employee` вместо стандартной `auth.User`), нужно сбросить БД
и применить миграции с нуля.

В вашей БД сейчас только служебные таблицы Django, ничего ценного нет —
безопасно удалить.

---

## Команды по порядку

Выполняйте в **PowerShell** в папке `app` с активированным виртуальным
окружением (в начале строки должно быть `(venv)`).

### 1. Получить новый код

```powershell
git pull
```

### 2. Удалить старую БД

В **pgAdmin 4**:
1. PostgreSQL 16 → Databases → правый клик по `ticket_system` →
   **Delete/Drop** → **Yes**.
2. Правый клик по **Databases** → **Create** → **Database** →
   имя `ticket_system` → **Save**.

ИЛИ одной командой через psql (подставьте путь под свою версию PostgreSQL):

```powershell
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres -c "DROP DATABASE IF EXISTS ticket_system;"
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres -c "CREATE DATABASE ticket_system;"
```

### 3. Создать миграции из новых моделей

Django сам сгенерирует файл миграции на основе `models.py`:

```powershell
python manage.py makemigrations core
```

Должно вывести:
```
Migrations for 'core':
  core\migrations\0001_initial.py
    + Create model Role
    + Create model Service
    + Create model Status
    + Create model Priority
    + Create model Team
    + Create model Employee
    + Create model Client
    + Create model Request
    + Create model Comment
    + Create model Attachment
    + Create model StatusHistory
    + Create model RoutingRule
    + Create model FieldDefinition
    + Create model AuditLog
```

### 4. Применить миграции

```powershell
python manage.py migrate
```

Создадутся все таблицы: и встроенные Django (auth, sessions, admin,
contenttypes), и наши 14 таблиц.

### 5. Заполнить справочники

```powershell
python manage.py seed
```

Должно вывести:
```
  ролей:       создано 5, обновлено 0, всего 5
  статусов:    создано 6, обновлено 0, всего 6
  приоритетов: создано 4, обновлено 0, всего 4
  услуг:       создано 4, обновлено 0, всего 4
  групп:       создано 3, всего 3
Готово. Справочники заполнены.
```

### 6. Создать суперпользователя

Старый суперпользователь удалился вместе с БД — создаём заново:

```powershell
python manage.py createsuperuser
```

Введите username (например, `admin`), email (можно пропустить), пароль.

### 7. Запустить сервер

```powershell
python manage.py runserver
```

---

## Что должно быть видно

### Главная страница: http://127.0.0.1:8000/

Появятся карточки со счётчиками:
- Заявок: 0 (открытых: 0)
- Клиентов: 0
- **Услуг: 4**
- **Сотрудников: 1** (это вы — суперпользователь)
- Кастомных полей: 0

### Админка: http://127.0.0.1:8000/admin/

В левом меню должны быть разделы:
- **Учёт заявок**:
  - Аудит-журнал
  - Группы исполнителей
  - Заявки
  - Клиенты
  - Комментарии
  - Конструктор полей
  - Правила маршрутизации
  - Приоритеты (4 записи)
  - Роли (5 записей)
  - Сотрудники (1 запись — вы)
  - Статусы (6 записей)
  - Услуги (4 записи)
- **Аутентификация и авторизация**:
  - Группы пользователей

Зайдите в **Заявки → Добавить заявку** и попробуйте создать тестовую запись:
1. Сначала добавьте одного клиента (раздел «Клиенты»).
2. Заполните форму создания заявки — почти все поля выбираются из справочников.
3. Сохраните — она появится в списке.

---

## Что прислать в ответ

- ✅ **Скриншот главной страницы** со счётчиками — пойдёт в ВКР.
- ✅ **Скриншот админки** — список разделов слева.
- ✅ **Скриншот списка заявок** в админке после создания тестовой записи.
- Сообщение **«Шаг 1 готов»** — двинусь к Шагу 2 (страницы списка/карточки заявок для обычных пользователей, без админки).

Если что-то пошло не так — пришлите текст ошибки целиком.
