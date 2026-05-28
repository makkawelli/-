# ИС «Учёт заявок» — прототип

Информационная система учёта заявок на обслуживание клиентов.
Дипломный проект (ВКР). Стек: **Python 3.11+ / Django 5 / PostgreSQL 15+**.

> Это **Шаг 0** разработки прототипа: запуск пустого Django-проекта.
> На главной странице должно появиться сообщение «Прототип успешно запущен».
> Если у вас оно появилось — переходим к Шагу 1 (модели БД).

---

## Что нужно установить (один раз)

| Программа           | Версия       | Где скачать                                            |
|---------------------|--------------|--------------------------------------------------------|
| Python              | 3.11 или новее | https://www.python.org/downloads/windows/            |
| PostgreSQL          | 15 или новее | https://www.postgresql.org/download/windows/           |
| Git                 | любая актуальная | https://git-scm.com/download/win                   |
| (рекомендую) VS Code | любая актуальная | https://code.visualstudio.com/                     |

---

## Шаг 1. Установка Python

1. Перейдите по ссылке https://www.python.org/downloads/windows/ и скачайте
   последний установщик **Windows installer (64-bit)**.
2. Запустите установщик.
3. **ОЧЕНЬ ВАЖНО:** на первом экране установщика поставьте галочку
   **«Add python.exe to PATH»** (внизу окна). Без неё команда `python`
   не будет работать в терминале.
4. Нажмите **Install Now** и дождитесь завершения.
5. Откройте новое окно **PowerShell** (Win + R → введите `powershell` → Enter)
   и проверьте установку:
   ```powershell
   python --version
   pip --version
   ```
   Должно вывести что-то вроде:
   ```
   Python 3.12.4
   pip 24.0 from ...
   ```

---

## Шаг 2. Установка PostgreSQL

1. Перейдите на https://www.postgresql.org/download/windows/ и нажмите
   **Download the installer**. Скачается установщик от EDB.
2. Запустите установщик. Все пункты можно оставлять по умолчанию.
3. **Запомните пароль**, который зададите для пользователя `postgres`
   на этапе «Password». Дальше будем использовать пароль `postgres`,
   но вы можете поставить любой — главное запомнить.
4. Порт оставьте `5432`.
5. Locale — `Russian, Russia` или `Default locale`, на выбор.
6. На последнем экране **снимите** галочку «Stack Builder» — он не нужен.
7. Дождитесь окончания установки. В меню «Пуск» появится **pgAdmin 4** —
   графическая утилита для работы с PostgreSQL.

### Проверка PostgreSQL

Откройте **pgAdmin 4** из меню Пуск. При первом запуске он попросит задать
мастер-пароль (любой). Затем в левом дереве появится `PostgreSQL 16` —
дважды щёлкните, введите тот пароль, что задавали при установке. Если
открылось дерево баз — PostgreSQL работает.

---

## Шаг 3. Создание базы данных

В pgAdmin 4:

1. Раскройте `PostgreSQL 16` → **Databases**.
2. Кликните правой кнопкой по **Databases** → **Create** → **Database…**.
3. В поле **Database** введите `ticket_system` → **Save**.

Готово, БД создана. Если предпочитаете командную строку — то же самое
можно сделать через **psql** в PowerShell:

```powershell
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres -c "CREATE DATABASE ticket_system;"
```
(подставьте свой пароль, когда спросит).

---

## Шаг 4. Скачивание проекта

Откройте PowerShell в той папке, где удобно держать проекты,
например `C:\Users\<Имя>\Projects`. Если папки нет — создайте:

```powershell
mkdir C:\Users\$env:USERNAME\Projects
cd    C:\Users\$env:USERNAME\Projects
```

Клонируйте репозиторий и переключитесь на нужную ветку:

```powershell
git clone https://github.com/makkawelli/-.git ticket-system
cd ticket-system
git checkout diploma
cd app
```

> Все дальнейшие команды выполняются **из папки `app`**.
> Можно открыть её в VS Code командой `code .` — будет удобнее редактировать файлы.

---

## Шаг 5. Виртуальное окружение и зависимости

Виртуальное окружение (venv) — это изолированная папка с библиотеками
именно для этого проекта. Зачем нужно: чтобы Django, установленный
для диплома, не конфликтовал с другими Python-проектами на компьютере.

```powershell
# 1) Создаём виртуальное окружение в папке venv\
python -m venv venv

# 2) Активируем его. Если PowerShell ругнётся на политику —
#    выполните один раз:
#       Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
.\venv\Scripts\Activate.ps1

# После активации в начале строки появится "(venv)".
# 3) Устанавливаем зависимости.
pip install -r requirements.txt
```

Установка займёт ~30 секунд. По завершении `pip list` должен показать
Django, psycopg, python-dotenv и пару зависимостей.

---

## Шаг 6. Настройка переменных окружения

В папке `app` есть файл `.env.example` — это образец. Скопируйте его в `.env`:

```powershell
copy .env.example .env
```

Откройте `.env` в любом текстовом редакторе и проверьте/исправьте две вещи:

1. **`DJANGO_SECRET_KEY`** — замените на любую длинную случайную строку.
   Сгенерировать можно командой:
   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(50))"
   ```
   и скопировать результат в `.env`.
2. **`POSTGRES_PASSWORD`** — поставьте тот пароль, который задавали при
   установке PostgreSQL (см. Шаг 2).

Остальные переменные (имя БД `ticket_system`, пользователь `postgres`,
хост `127.0.0.1`, порт `5432`) уже совпадают с теми, что мы задали выше.

---

## Шаг 7. Применение миграций

Миграции — это инструкции для создания таблиц в БД. На этом этапе мы ещё
не описали свои модели, поэтому Django применит только встроенные миграции
(пользователи, сессии, админка).

```powershell
python manage.py migrate
```

Если всё хорошо — увидите длинный список `Applying ... OK`.

### Если выдало ошибку подключения к БД
- Проверьте, что в pgAdmin 4 БД `ticket_system` действительно создана.
- Проверьте, что в `.env` правильный `POSTGRES_PASSWORD`.
- Проверьте, что служба PostgreSQL запущена: Win + R → `services.msc` → найдите
  **postgresql-x64-16** → должно быть «Выполняется».

---

## Шаг 8. Создание администратора

Чтобы зайти в админку Django, нужен суперпользователь:

```powershell
python manage.py createsuperuser
```

Введите имя (например, `admin`), email (можно пропустить, нажав Enter),
пароль (минимум 8 символов; короткий пароль Django примет, если ответить «y»
на вопрос «Bypass password validation»).

---

## Шаг 9. Запуск сервера

```powershell
python manage.py runserver
```

В консоли появится:

```
Starting development server at http://127.0.0.1:8000/
Quit the server with CTRL-BREAK.
```

Откройте в браузере http://127.0.0.1:8000/ — должна появиться карточка
**«Информационная система учёта заявок — Прототип успешно запущен»**.

Параллельно проверьте админку: http://127.0.0.1:8000/admin/ — войдите
учёткой администратора, созданной на Шаге 8.

---

## Что делать дальше

Если всё работает:

1. Сделайте скриншот главной страницы и страницы админки — пригодятся для главы 3 ВКР.
2. Сообщите мне в чате «**Шаг 0 готов**».
3. Перехожу к **Шагу 1**: опишу модели БД по `schema.sql`,
   создам миграции — после этого в админке появятся все наши таблицы
   (Клиенты, Заявки, Услуги, Статусы и т. д.).

В следующих циклах разработки:
```powershell
# когда я внесу изменения в код:
git pull

# если в новом шаге появились новые зависимости:
pip install -r requirements.txt

# применить новые миграции:
python manage.py migrate

# запустить сервер:
python manage.py runserver
```

---

## Типичные проблемы и их решения

### `python : The term 'python' is not recognized`
Не поставлена галочка «Add Python to PATH» при установке. Удалите Python
через «Параметры → Приложения», установите заново с галочкой.

### `psycopg.OperationalError: FATAL: password authentication failed`
В `.env` неверный `POSTGRES_PASSWORD`. Проверьте, под каким паролем
PostgreSQL был установлен.

### `psycopg.OperationalError: connection ... refused`
Служба PostgreSQL не запущена. `services.msc` → запустите `postgresql-x64-16`.

### `django.db.utils.OperationalError: FATAL: database "ticket_system" does not exist`
БД не создана. Вернитесь к Шагу 3.

### При активации venv в PowerShell:
`...cannot be loaded because running scripts is disabled on this system`

Один раз выполните:
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```
и подтвердите `Y`.

### Какой-то другой непонятный текст ошибки
Скопируйте **всё**, что вывело в консоль, и пришлите мне в чат —
разберёмся.

---

## Структура проекта (для понимания)

```
app/
├── manage.py                  # CLI-утилита Django
├── requirements.txt           # список Python-зависимостей
├── .env.example               # образец настроек (коммитится)
├── .env                       # реальные настройки (НЕ коммитится)
├── .gitignore
├── README.md                  # этот файл
├── ticket_system/             # «Project» — глобальные настройки
│   ├── settings.py            # конфигурация (БД, шаблоны, приложения...)
│   ├── urls.py                # главный роутер URL
│   ├── wsgi.py / asgi.py      # точки входа для production-серверов
│   └── __init__.py
├── core/                      # «App» — наша бизнес-логика
│   ├── apps.py
│   ├── admin.py               # регистрация моделей в админке
│   ├── models.py              # ORM-модели (пока пусто, наполним на Шаге 1)
│   ├── views.py               # контроллеры (страницы)
│   ├── urls.py                # маршруты приложения
│   ├── migrations/            # автогенерируемые миграции БД
│   └── templates/core/        # HTML-шаблоны приложения
│       └── home.html
└── templates/                 # глобальные шаблоны (общая обвязка)
    └── base.html
```
