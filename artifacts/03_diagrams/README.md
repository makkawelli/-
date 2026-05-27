# Диаграммы для ВКР

В папке лежат исходники четырёх диаграмм в формате **PlantUML** (`.puml`):

| Файл | Что показывает | Глава ВКР |
|---|---|---|
| `use_case.puml` | Диаграмма вариантов использования (UML Use Case) | 2.2.1 |
| `bpmn_as_is.puml` | Бизнес-процесс «AS-IS» (до внедрения ИС) | 1.3.2 |
| `bpmn_to_be.puml` | Бизнес-процесс «TO-BE» (после внедрения ИС) | 1.4.1 / 2.2.3 |
| `activity_request_lifecycle.puml` | Диаграмма деятельности — жизненный цикл заявки | 2.2.3 |

## Как получить картинки (PNG/SVG) для вставки в DOCX

### Способ 1 — онлайн-сервис PlantUML (быстрее всего)
1. Открыть https://www.plantuml.com/plantuml/uml
2. Скопировать содержимое `.puml`-файла в текстовое поле.
3. Внизу выбрать формат: **PNG** или **SVG**.
4. Скачать и вставить в Word (`Вставка → Рисунок`).

### Способ 2 — VS Code с расширением PlantUML
1. Установить расширение **PlantUML** (jebbs.plantuml).
2. Открыть `.puml`-файл, нажать `Alt+D` — превью.
3. `Ctrl+Shift+P` → **PlantUML: Export Current Diagram** → выбрать PNG.
4. Файл будет сохранён рядом.

### Способ 3 — локально через JAR
```bash
# скачать plantuml.jar один раз с plantuml.com/download
java -jar plantuml.jar -tpng artifacts/03_diagrams/*.puml
# результат - .png рядом с .puml
```

## Альтернатива — Mermaid (рендерится прямо на GitHub)

Ниже — те же диаграммы в Mermaid-версии. GitHub отрисует их в превью этого README автоматически. Также можно открыть https://mermaid.live для редактирования.

### 1. Use Case (упрощённый, в нотации Mermaid `flowchart`)

```mermaid
flowchart LR
    Client((Клиент)):::actor
    Operator((Оператор)):::actor
    Executor((Исполнитель)):::actor
    Manager((Менеджер)):::actor
    Admin((Админ)):::actor

    subgraph System["ИС учёта заявок"]
        UC01[UC-01 Создать заявку]
        UC02[UC-02 Список заявок]
        UC03[UC-03 Карточка заявки]
        UC07[UC-07 Назначить исполнителя]
        UC08[UC-08 Изменить статус]
        UC10[UC-10 Закрыть заявку]
        UC11[UC-11 Дашборд]
        UC12[UC-12 Отчёт]
        UC14[UC-14 Управлять пользователями]
        UC17[UC-17 Кастомные поля]
    end

    Client --> UC01
    Client --> UC02
    Client --> UC03
    Operator --> UC01
    Operator --> UC07
    Executor --> UC02
    Executor --> UC03
    Executor --> UC08
    Manager --> UC07
    Manager --> UC10
    Manager --> UC11
    Manager --> UC12
    Admin --> UC14
    Admin --> UC17

    classDef actor fill:#fff,stroke:#333,stroke-width:2px
```

### 2. AS-IS процесс

```mermaid
flowchart TB
    A([Клиент: возникла потребность]) --> B[Выбирает канал:<br>телефон / email / мессенджер]
    B --> C[Оператор фиксирует заявку<br>в блокноте/Excel/письме]
    C --> D{Заявка зафиксирована<br>корректно?}
    D -- нет --> X1[Потеря заявки]:::bad
    D -- да --> E[Передача исполнителю<br>устно/в чате/письмом]
    E --> F{Дошла до<br>исполнителя?}
    F -- нет --> X2[Потеря на передаче]:::bad
    F -- да --> G[Исполнитель выполняет работу]
    G --> H[Сообщает оператору]
    H --> I{Менеджер хочет<br>метрики?}
    I -- да --> X3[Сбор данных вручную<br>из разных источников]:::bad
    I -- нет --> J([Клиент получает результат<br>или звонит повторно])

    classDef bad fill:#FFCDD2,stroke:#B71C1C
```

### 3. TO-BE процесс

```mermaid
flowchart TB
    A([Клиент: создаёт заявку<br>через единое окно]) --> B[ИС: сохранение,<br>генерация номера]
    B --> C{Сработало правило<br>маршрутизации?}
    C -- да --> D[Email оператору группы]
    C -- нет --> E[Очередь ручной<br>маршрутизации]
    D --> F[Оператор: назначает исполнителя]
    E --> F
    F --> G[ИС: статус=in_progress<br>email клиенту и исполнителю]
    G --> H[Исполнитель работает<br>с комментариями и вложениями]
    H --> H1{Приостановка?}
    H1 -- да --> H2[status=on_hold]
    H2 --> H
    H1 -- нет --> I[Передача на проверку<br>status=review]
    I --> J{Менеджер принял?}
    J -- нет --> H
    J -- да --> K[status=done<br>closed_at=NOW]
    K --> L[Email клиенту,<br>audit_log,<br>дашборд обновлён]
    L --> M([Клиент получил результат])

    style B fill:#E1F5FE
    style G fill:#E1F5FE
    style K fill:#E1F5FE
    style L fill:#E1F5FE
```

### 4. Жизненный цикл заявки (state machine)

```mermaid
stateDiagram-v2
    [*] --> new: регистрация
    new --> in_progress: назначить исполнителя
    in_progress --> on_hold: приостановить (с причиной)
    on_hold --> in_progress: возобновить
    in_progress --> review: исполнитель сдал
    review --> in_progress: менеджер вернул на доработку
    review --> done: менеджер принял
    in_progress --> cancelled: отмена клиентом/менеджером
    new --> cancelled: отмена до старта
    on_hold --> cancelled: отмена во время простоя
    done --> [*]
    cancelled --> [*]

    note right of done
        is_terminal = true
        closed_at = NOW()
    end note
    note right of cancelled
        is_terminal = true
        closed_at = NOW()
    end note
```

## Какой формат выбрать

- **Для самой ВКР (DOCX)** — рендерить PlantUML-исходники в **PNG** через plantuml.com и вставлять как рисунки. Это даёт максимально презентабельный вид и гибкость стилей.
- **Для черновой работы и обсуждения** — Mermaid в `.md`-файле в репозитории, GitHub показывает их сразу.
- **При защите (на слайдах)** — лучше тоже PNG/SVG из PlantUML.
