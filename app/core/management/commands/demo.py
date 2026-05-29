"""Заполнение БД демонстрационными данными.

Использование:
    python manage.py demo

Команда идемпотентна: повторный запуск не дублирует записи.
Создаёт:
    - 4 тестовых сотрудника разных ролей (manager, operator, executor1, executor2)
    - 5 клиентов
    - 3 пользовательских поля (low-code)
    - 14 заявок в разных статусах с историей и комментариями

ВНИМАНИЕ: команда требует, чтобы справочники (роли, статусы, приоритеты, услуги,
группы) были предварительно заполнены через `python manage.py seed`.
"""
import random
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core import models


# Единый пароль для всех демо-пользователей. Для разработки удобно,
# на боевом окружении такого, разумеется, никогда не делается.
DEMO_PASSWORD = "demo1234"


# =============================================================================
# Описание тестовых пользователей
# =============================================================================
# is_staff намеренно False у всех:
# Django Admin использует свою систему прав (auth.Permission), которые
# мы не настраиваем — менеджер/оператор/исполнитель пользуются нашим
# собственным UI. Включение is_staff без настройки прав давало лишь
# пустую админ-панель и путало пользователя.
# Полноценный доступ к админке — только у суперпользователя (admin,
# создаётся отдельно через python manage.py createsuperuser).
EMPLOYEES = [
    {
        "username": "manager",
        "full_name": "Иванов Иван Иванович",
        "position": "Руководитель сервиса",
        "email": "manager@ticket-system.local",
        "role_code": "manager",
        "is_staff": False,
    },
    {
        "username": "operator",
        "full_name": "Петрова Мария Сергеевна",
        "position": "Диспетчер",
        "email": "operator@ticket-system.local",
        "role_code": "operator",
        "is_staff": False,
    },
    {
        "username": "executor1",
        "full_name": "Сидоров Алексей Викторович",
        "position": "Инженер технической поддержки",
        "email": "executor1@ticket-system.local",
        "role_code": "executor",
        "is_staff": False,
    },
    {
        "username": "executor2",
        "full_name": "Кузнецов Дмитрий Олегович",
        "position": "Сетевой инженер",
        "email": "executor2@ticket-system.local",
        "role_code": "executor",
        "is_staff": False,
    },
]

# =============================================================================
# Описание клиентов
# =============================================================================
CLIENTS = [
    {"name": "ООО «Ромашка»",       "contact_person": "Семёнов Иван Петрович",   "phone": "+7 (495) 100-20-30", "email": "info@romashka.example"},
    {"name": "ИП Иванов А.А.",       "contact_person": "Иванов Антон Алексеевич", "phone": "+7 (916) 555-12-34", "email": "ivanov.aa@example.com"},
    {"name": "ООО «ТехноСервис»",    "contact_person": "Орлова Елена Сергеевна",  "phone": "+7 (812) 200-30-40", "email": "office@technoservice.example"},
    {"name": "ЗАО «Альфа-Холдинг»",  "contact_person": "Волков Сергей Михайлович", "phone": "+7 (495) 700-80-90", "email": "support@alfa-holding.example"},
    {"name": "ООО «СтройМаркет»",    "contact_person": "Кузьмина Анна Викторовна", "phone": "+7 (343) 222-33-44", "email": "info@stroymarket.example"},
]

# =============================================================================
# Описание low-code полей
# =============================================================================
FIELD_DEFINITIONS = [
    {
        "code": "device_serial",
        "label": "Серийный номер устройства",
        "field_type": "text",
        "is_required": False,
        "order_num": 10,
    },
    {
        "code": "client_urgency",
        "label": "Срочность по мнению клиента",
        "field_type": "select",
        "options": ["Не срочно", "Можно подождать", "Срочно"],
        "is_required": False,
        "order_num": 20,
    },
    {
        "code": "paid_express_visit",
        "label": "Готов оплатить срочный выезд",
        "field_type": "checkbox",
        "is_required": False,
        "order_num": 30,
    },
]

# =============================================================================
# Сценарии заявок
# =============================================================================
REQUESTS = [
    # --- Новые ---
    {
        "title": "Не работает интернет в офисе",
        "description": "С утра пропал интернет на всех рабочих местах. Маршрутизатор перезагружали — не помогло.",
        "client": "ООО «Ромашка»", "service": "Сетевые работы",
        "status": "new", "priority": "high",
        "created_by": "operator", "assignee": None,
        "days_ago": 0,
        "custom_fields": {"client_urgency": "Срочно"},
        "comments": [],
    },
    {
        "title": "Установить новую версию 1С",
        "description": "Просьба обновить «1С:Бухгалтерия» с 8.3.20 до последней.",
        "client": "ИП Иванов А.А.", "service": "Настройка ПО",
        "status": "new", "priority": "low",
        "created_by": "operator", "assignee": None,
        "days_ago": 1,
        "custom_fields": {"client_urgency": "Не срочно"},
        "comments": [],
    },
    {
        "title": "Принтер печатает с полосами",
        "description": "Принтер HP LaserJet 1320 печатает с горизонтальными полосами. Картридж недавно меняли.",
        "client": "ООО «ТехноСервис»", "service": "Ремонт оборудования",
        "status": "new", "priority": "medium",
        "created_by": "operator", "assignee": None,
        "days_ago": 0,
        "custom_fields": {"device_serial": "VNB3K12345"},
        "comments": [],
    },

    # --- В работе ---
    {
        "title": "Не подключается VPN",
        "description": "После обновления Windows перестал работать корпоративный VPN. Ошибка: «Не удалось установить туннельное соединение».",
        "client": "ЗАО «Альфа-Холдинг»", "service": "Сетевые работы",
        "status": "in_progress", "priority": "high",
        "created_by": "operator", "assignee": "executor2",
        "days_ago": 2,
        "custom_fields": {"client_urgency": "Срочно", "paid_express_visit": True},
        "comments": [
            ("Принял в работу. Посмотрю настройки клиента VPN.", True),
            ("Уважаемый клиент, специалист уже работает над вашей заявкой.", False),
        ],
    },
    {
        "title": "Перенастроить почтовый клиент",
        "description": "Сменили домен на новый, нужно перенастроить Outlook у 5 сотрудников.",
        "client": "ООО «Ромашка»", "service": "Настройка ПО",
        "status": "in_progress", "priority": "medium",
        "created_by": "operator", "assignee": "executor1",
        "days_ago": 3,
        "custom_fields": {},
        "comments": [
            ("Подготовил инструкцию, начинаю обходить рабочие места.", True),
        ],
    },
    {
        "title": "Установка нового МФУ",
        "description": "Подключить новое МФУ Kyocera, развернуть драйверы по сети.",
        "client": "ООО «СтройМаркет»", "service": "Настройка ПО",
        "status": "in_progress", "priority": "low",
        "created_by": "operator", "assignee": "executor1",
        "days_ago": 5,
        "custom_fields": {"device_serial": "KCM8901234"},
        "comments": [],
    },
    {
        "title": "Консультация по 1С — закрытие месяца",
        "description": "Нужно разобраться с регламентным закрытием месяца, бухгалтер просит помочь.",
        "client": "ИП Иванов А.А.", "service": "Консультация",
        "status": "in_progress", "priority": "medium",
        "created_by": "operator", "assignee": "executor1",
        "days_ago": 1,
        "custom_fields": {},
        "comments": [],
    },

    # --- На проверке ---
    {
        "title": "Заменить кабель на рабочем месте",
        "description": "Перебитый патч-корд у оператора. Нужно заменить.",
        "client": "ООО «ТехноСервис»", "service": "Ремонт оборудования",
        "status": "review", "priority": "low",
        "created_by": "operator", "assignee": "executor2",
        "days_ago": 4,
        "custom_fields": {},
        "comments": [
            ("Кабель заменил, прошу проверить.", True),
        ],
    },
    {
        "title": "Настроить резервное копирование сервера",
        "description": "Развернуть Veeam, настроить ежедневный бэкап.",
        "client": "ЗАО «Альфа-Холдинг»", "service": "Настройка ПО",
        "status": "review", "priority": "high",
        "created_by": "manager", "assignee": "executor2",
        "days_ago": 6,
        "custom_fields": {"client_urgency": "Срочно"},
        "comments": [
            ("Veeam установлен, политика бэкапа настроена. Прошу принять работу.", True),
        ],
    },

    # --- Приостановлена ---
    {
        "title": "Заменить диск в RAID",
        "description": "В RAID-массиве вышел из строя один диск. Ждём поставку.",
        "client": "ООО «СтройМаркет»", "service": "Ремонт оборудования",
        "status": "on_hold", "priority": "high",
        "created_by": "operator", "assignee": "executor2",
        "days_ago": 7,
        "custom_fields": {"device_serial": "WD8TBR-001"},
        "comments": [
            ("Заказали диск у поставщика, ожидаемая дата поставки — через 5 рабочих дней.", False),
        ],
    },

    # --- Выполнена ---
    {
        "title": "Подключить нового сотрудника",
        "description": "Создать учётные записи в AD и почте для нового бухгалтера.",
        "client": "ООО «Ромашка»", "service": "Настройка ПО",
        "status": "done", "priority": "medium",
        "created_by": "operator", "assignee": "executor1",
        "days_ago": 10,
        "custom_fields": {},
        "comments": [
            ("Учётки созданы, пароли переданы лично.", True),
            ("Здравствуйте! Учётные записи созданы. Пароли отправлены сотруднику в личном порядке.", False),
        ],
    },
    {
        "title": "Чистка системного блока от пыли",
        "description": "Профилактика — почистить ПК главного бухгалтера.",
        "client": "ИП Иванов А.А.", "service": "Ремонт оборудования",
        "status": "done", "priority": "low",
        "created_by": "operator", "assignee": "executor2",
        "days_ago": 14,
        "custom_fields": {},
        "comments": [
            ("ПК почистил, заменил термопасту. Температура процессора в норме.", True),
        ],
    },
    {
        "title": "Настройка Wi-Fi в переговорной",
        "description": "Усилить сигнал Wi-Fi в большой переговорной (точка доступа уже есть).",
        "client": "ЗАО «Альфа-Холдинг»", "service": "Сетевые работы",
        "status": "done", "priority": "medium",
        "created_by": "operator", "assignee": "executor2",
        "days_ago": 12,
        "custom_fields": {},
        "comments": [],
    },

    # --- Отменена ---
    {
        "title": "Установка устаревшего программного обеспечения",
        "description": "Просили установить Windows XP на новый ПК. После переговоров отказались.",
        "client": "ООО «СтройМаркет»", "service": "Настройка ПО",
        "status": "cancelled", "priority": "low",
        "created_by": "operator", "assignee": None,
        "days_ago": 8,
        "custom_fields": {},
        "comments": [
            ("Клиент перезвонил и отозвал заявку — нашли подходящее современное решение.", False),
        ],
    },
]


class Command(BaseCommand):
    help = "Заполнить БД демонстрационными данными для разработки и скриншотов."

    @transaction.atomic
    def handle(self, *args, **options):
        self._check_seed_present()

        self.stdout.write(self.style.MIGRATE_HEADING("Создание сотрудников..."))
        employees = self._create_employees()

        self.stdout.write(self.style.MIGRATE_HEADING("Создание клиентов..."))
        clients = self._create_clients()

        self.stdout.write(self.style.MIGRATE_HEADING("Создание low-code полей..."))
        self._create_field_definitions()

        self.stdout.write(self.style.MIGRATE_HEADING("Создание заявок..."))
        self._create_requests(employees, clients)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Готово!"))
        self.stdout.write("")
        self.stdout.write("Тестовые учётные записи (пароль у всех — demo1234):")
        for emp in EMPLOYEES:
            self.stdout.write(f"    {emp['username']:<10s}  ({emp['role_code']:<8s})  {emp['full_name']}")
        self.stdout.write("")
        self.stdout.write("Заходите в http://127.0.0.1:8000/admin/ под этими учётками,")
        self.stdout.write("чтобы увидеть, как админка выглядит для разных ролей.")

    # =========================================================================
    # Проверка предварительных условий
    # =========================================================================
    def _check_seed_present(self) -> None:
        missing = []
        if not models.Role.objects.exists():
            missing.append("роли")
        if not models.Status.objects.exists():
            missing.append("статусы")
        if not models.Priority.objects.exists():
            missing.append("приоритеты")
        if not models.Service.objects.exists():
            missing.append("услуги")
        if missing:
            raise CommandError(
                "Не заполнены справочники: " + ", ".join(missing) + ".\n"
                "Сначала выполните: python manage.py seed"
            )

    # =========================================================================
    # Сотрудники
    # =========================================================================
    def _create_employees(self) -> dict:
        result = {}
        for spec in EMPLOYEES:
            role = models.Role.objects.get(code=spec["role_code"])
            employee, created = models.Employee.objects.get_or_create(
                username=spec["username"],
                defaults={
                    "full_name": spec["full_name"],
                    "position": spec["position"],
                    "email": spec["email"],
                    "role": role,
                    "is_staff": spec["is_staff"],
                    "is_active": True,
                },
            )
            if created:
                employee.set_password(DEMO_PASSWORD)
                employee.save()
                self.stdout.write(f"  + {employee.username} ({role})")
            else:
                # Обновляем поля для существующих пользователей — на случай,
                # если семантика is_staff/role изменилась между запусками demo.
                changed = False
                if employee.role_id != role.id:
                    employee.role = role
                    changed = True
                if employee.is_staff != spec["is_staff"]:
                    employee.is_staff = spec["is_staff"]
                    changed = True
                if changed:
                    employee.save(update_fields=["role", "is_staff"])
                    self.stdout.write(f"  ~ {employee.username} обновлён (role/is_staff)")
                else:
                    self.stdout.write(f"  - {employee.username} уже существует, пропускаю")
            result[spec["username"]] = employee
        return result

    # =========================================================================
    # Клиенты
    # =========================================================================
    def _create_clients(self) -> dict:
        result = {}
        for spec in CLIENTS:
            client, created = models.Client.objects.get_or_create(
                name=spec["name"],
                defaults={
                    "contact_person": spec["contact_person"],
                    "phone": spec["phone"],
                    "email": spec["email"],
                },
            )
            if created:
                self.stdout.write(f"  + {client.name}")
            result[spec["name"]] = client
        return result

    # =========================================================================
    # Low-code поля
    # =========================================================================
    def _create_field_definitions(self) -> None:
        for spec in FIELD_DEFINITIONS:
            obj, created = models.FieldDefinition.objects.get_or_create(
                code=spec["code"],
                defaults={
                    "label": spec["label"],
                    "field_type": spec["field_type"],
                    "options": spec.get("options"),
                    "is_required": spec["is_required"],
                    "order_num": spec["order_num"],
                    "is_active": True,
                },
            )
            if created:
                self.stdout.write(f"  + {obj.label} ({obj.field_type})")

    # =========================================================================
    # Заявки
    # =========================================================================
    def _create_requests(self, employees: dict, clients: dict) -> None:
        existing_numbers = set(
            models.Request.objects.values_list("number", flat=True)
        )
        next_seq = self._next_request_number_seq(existing_numbers)
        year = timezone.now().year

        services = {s.name: s for s in models.Service.objects.all()}
        statuses = {s.code: s for s in models.Status.objects.all()}
        priorities = {p.code: p for p in models.Priority.objects.all()}

        new_status = statuses["new"]

        created_count = 0
        for spec in REQUESTS:
            client = clients[spec["client"]]
            # Идемпотентность: если такая заявка уже была создана demo-командой,
            # пропускаем.
            if models.Request.objects.filter(title=spec["title"], client=client).exists():
                continue

            number = f"REQ-{year}-{next_seq:06d}"
            status = statuses[spec["status"]]
            priority = priorities[spec["priority"]]
            service = services[spec["service"]]
            assignee = employees.get(spec["assignee"]) if spec["assignee"] else None
            created_by = employees[spec["created_by"]]

            now = timezone.now()
            created_at = now - timedelta(days=spec["days_ago"], hours=random.randint(0, 12))
            due_date = created_at + timedelta(hours=priority.sla_hours)
            closed_at = (
                created_at + timedelta(hours=max(1, priority.sla_hours - random.randint(1, 3)))
                if status.is_terminal else None
            )

            req = models.Request.objects.create(
                number=number,
                client=client,
                service=service,
                status=status,
                priority=priority,
                assignee=assignee,
                created_by=created_by,
                title=spec["title"],
                description=spec["description"],
                due_date=due_date,
                custom_fields=spec.get("custom_fields") or {},
            )
            # auto_now_add нельзя обойти при .create(),
            # обновляем created_at и closed_at отдельным UPDATE-запросом.
            models.Request.objects.filter(pk=req.pk).update(
                created_at=created_at,
                updated_at=created_at,
                closed_at=closed_at,
            )
            req.refresh_from_db()

            # Запись в history: «создана» (status_from = NULL, status_to = new).
            self._add_history(req, None, new_status, created_by, created_at,
                              "Заявка создана.")

            # Если статус не «new» — добавляем переход new -> текущий статус.
            if status.code != "new":
                changed_at = created_at + timedelta(hours=random.randint(1, 6))
                self._add_history(req, new_status, status, created_by, changed_at)

            # Комментарии.
            for text, is_internal in spec.get("comments", []):
                models.Comment.objects.create(
                    request=req,
                    author=assignee or created_by,
                    text=text,
                    is_internal=is_internal,
                )

            self.stdout.write(f"  + {number} [{status.code}] {req.title}")
            created_count += 1
            next_seq += 1

        if created_count == 0:
            self.stdout.write("  - все demo-заявки уже созданы, пропускаю.")

    @staticmethod
    def _next_request_number_seq(existing: set[str]) -> int:
        max_seq = 0
        for n in existing:
            try:
                seq = int(n.split("-")[-1])
                max_seq = max(max_seq, seq)
            except (ValueError, IndexError):
                continue
        return max_seq + 1

    @staticmethod
    def _add_history(req, status_from, status_to, who, when, comment: str = "") -> None:
        h = models.StatusHistory.objects.create(
            request=req,
            status_from=status_from,
            status_to=status_to,
            changed_by=who,
            comment=comment,
        )
        # auto_now_add игнорирует значение в create(), поэтому update() явно.
        models.StatusHistory.objects.filter(pk=h.pk).update(changed_at=when)
