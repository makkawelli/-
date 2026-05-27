-- =============================================================================
-- Схема БД информационной системы учёта заявок на обслуживание клиентов
-- СУБД: PostgreSQL 15+
-- Кодировка: UTF-8
-- Автор: ВКР, 2026
-- =============================================================================

-- Расширения
CREATE EXTENSION IF NOT EXISTS pg_trgm;       -- триграммный поиск по тексту
CREATE EXTENSION IF NOT EXISTS pgcrypto;      -- gen_random_uuid (на будущее)

BEGIN;

-- =============================================================================
-- 1. СПРАВОЧНИКИ
-- =============================================================================

CREATE TABLE role (
    id          SMALLSERIAL PRIMARY KEY,
    code        VARCHAR(32) NOT NULL UNIQUE,
    name        VARCHAR(64) NOT NULL
);
COMMENT ON TABLE role IS 'Роли пользователей системы';

CREATE TABLE service (
    id                     SERIAL PRIMARY KEY,
    name                   VARCHAR(128) NOT NULL,
    description            TEXT,
    default_duration_hours INTEGER CHECK (default_duration_hours > 0),
    is_active              BOOLEAN NOT NULL DEFAULT TRUE
);
COMMENT ON TABLE service IS 'Каталог оказываемых услуг';

CREATE TABLE status (
    id          SMALLSERIAL PRIMARY KEY,
    code        VARCHAR(32) NOT NULL UNIQUE,
    name        VARCHAR(64) NOT NULL,
    order_num   SMALLINT NOT NULL DEFAULT 100,
    is_terminal BOOLEAN NOT NULL DEFAULT FALSE
);
COMMENT ON TABLE status IS 'Возможные статусы заявки';

CREATE TABLE priority (
    id        SMALLSERIAL PRIMARY KEY,
    code      VARCHAR(16) NOT NULL UNIQUE,
    name      VARCHAR(32) NOT NULL,
    sla_hours INTEGER NOT NULL CHECK (sla_hours > 0)
);
COMMENT ON TABLE priority IS 'Приоритеты заявок и нормативы SLA';

CREATE TABLE team (
    id   SERIAL PRIMARY KEY,
    name VARCHAR(128) NOT NULL UNIQUE
);
COMMENT ON TABLE team IS 'Группы исполнителей';

-- =============================================================================
-- 2. ПОЛЬЗОВАТЕЛИ И КЛИЕНТЫ
-- =============================================================================

CREATE TABLE employee (
    id            SERIAL PRIMARY KEY,
    full_name     VARCHAR(255) NOT NULL,
    position      VARCHAR(128),
    login         VARCHAR(64)  NOT NULL UNIQUE,
    email         VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role_id       SMALLINT     NOT NULL REFERENCES role(id) ON DELETE RESTRICT,
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE employee IS 'Сотрудники - пользователи системы';
CREATE INDEX idx_employee_role     ON employee(role_id);
CREATE INDEX idx_employee_is_active ON employee(is_active);

CREATE TABLE employee_team (
    employee_id INTEGER NOT NULL REFERENCES employee(id) ON DELETE CASCADE,
    team_id     INTEGER NOT NULL REFERENCES team(id)     ON DELETE CASCADE,
    PRIMARY KEY (employee_id, team_id)
);
COMMENT ON TABLE employee_team IS 'Связь сотрудников с группами (M:N)';

CREATE TABLE client (
    id             SERIAL PRIMARY KEY,
    name           VARCHAR(255) NOT NULL,
    contact_person VARCHAR(255),
    phone          VARCHAR(32),
    email          VARCHAR(255),
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE client IS 'Клиенты (контрагенты)';
CREATE INDEX idx_client_phone ON client(phone);
CREATE INDEX idx_client_email ON client(email);
CREATE INDEX idx_client_name_trgm ON client USING GIN (name gin_trgm_ops);

-- =============================================================================
-- 3. ЯДРО: ЗАЯВКИ
-- =============================================================================

CREATE TABLE request (
    id            BIGSERIAL    PRIMARY KEY,
    number        VARCHAR(32)  NOT NULL UNIQUE,
    client_id     INTEGER      NOT NULL REFERENCES client(id)   ON DELETE RESTRICT,
    service_id   INTEGER      NOT NULL REFERENCES service(id)  ON DELETE RESTRICT,
    status_id     SMALLINT     NOT NULL REFERENCES status(id)   ON DELETE RESTRICT,
    priority_id   SMALLINT     NOT NULL REFERENCES priority(id) ON DELETE RESTRICT,
    assignee_id   INTEGER               REFERENCES employee(id) ON DELETE SET NULL,
    created_by    INTEGER      NOT NULL REFERENCES employee(id) ON DELETE RESTRICT,
    title         VARCHAR(255) NOT NULL,
    description   TEXT,
    due_date      TIMESTAMPTZ,
    closed_at     TIMESTAMPTZ,
    custom_fields JSONB        NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE request IS 'Заявки на обслуживание - центральная сущность системы';
COMMENT ON COLUMN request.custom_fields IS 'Значения low-code-полей; описания в field_definition';

CREATE INDEX idx_request_client       ON request(client_id);
CREATE INDEX idx_request_assignee     ON request(assignee_id);
CREATE INDEX idx_request_status       ON request(status_id);
CREATE INDEX idx_request_priority     ON request(priority_id);
CREATE INDEX idx_request_service      ON request(service_id);
CREATE INDEX idx_request_created_at   ON request(created_at DESC);
CREATE INDEX idx_request_custom       ON request USING GIN (custom_fields);
CREATE INDEX idx_request_search       ON request USING GIN (
    to_tsvector('russian', coalesce(title, '') || ' ' || coalesce(description, ''))
);

-- Триггер автообновления updated_at
CREATE OR REPLACE FUNCTION trg_set_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER request_set_updated_at
    BEFORE UPDATE ON request
    FOR EACH ROW EXECUTE FUNCTION trg_set_updated_at();

-- Триггер автозаполнения closed_at при переходе в финальный статус
CREATE OR REPLACE FUNCTION trg_request_set_closed_at() RETURNS TRIGGER AS $$
DECLARE
    v_is_terminal BOOLEAN;
BEGIN
    SELECT is_terminal INTO v_is_terminal FROM status WHERE id = NEW.status_id;
    IF v_is_terminal AND NEW.closed_at IS NULL THEN
        NEW.closed_at := NOW();
    ELSIF NOT v_is_terminal THEN
        NEW.closed_at := NULL;  -- открыли заново
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER request_set_closed_at
    BEFORE INSERT OR UPDATE OF status_id ON request
    FOR EACH ROW EXECUTE FUNCTION trg_request_set_closed_at();

-- =============================================================================
-- 4. КОММЕНТАРИИ, ВЛОЖЕНИЯ, ИСТОРИЯ
-- =============================================================================

CREATE TABLE comment (
    id          BIGSERIAL   PRIMARY KEY,
    request_id  BIGINT      NOT NULL REFERENCES request(id)  ON DELETE CASCADE,
    author_id   INTEGER     NOT NULL REFERENCES employee(id) ON DELETE RESTRICT,
    text        TEXT        NOT NULL,
    is_internal BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE comment IS 'Комментарии к заявкам (история коммуникации)';
CREATE INDEX idx_comment_request ON comment(request_id, created_at DESC);

CREATE TABLE attachment (
    id          BIGSERIAL   PRIMARY KEY,
    request_id  BIGINT      NOT NULL REFERENCES request(id)  ON DELETE CASCADE,
    file_name   VARCHAR(255) NOT NULL,
    file_path   VARCHAR(512) NOT NULL,
    file_size   BIGINT       NOT NULL CHECK (file_size >= 0),
    mime_type   VARCHAR(128),
    uploaded_by INTEGER      NOT NULL REFERENCES employee(id) ON DELETE RESTRICT,
    uploaded_at TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE attachment IS 'Файловые вложения к заявкам';
CREATE INDEX idx_attachment_request ON attachment(request_id);

CREATE TABLE status_history (
    id              BIGSERIAL   PRIMARY KEY,
    request_id      BIGINT      NOT NULL REFERENCES request(id)  ON DELETE CASCADE,
    status_from_id  SMALLINT             REFERENCES status(id)   ON DELETE RESTRICT,
    status_to_id    SMALLINT    NOT NULL REFERENCES status(id)   ON DELETE RESTRICT,
    changed_by      INTEGER     NOT NULL REFERENCES employee(id) ON DELETE RESTRICT,
    comment         TEXT,
    changed_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE status_history IS 'История переходов между статусами';
CREATE INDEX idx_status_history_request ON status_history(request_id, changed_at);

-- =============================================================================
-- 5. МАРШРУТИЗАЦИЯ И LOW-CODE
-- =============================================================================

CREATE TABLE routing_rule (
    id             SERIAL    PRIMARY KEY,
    service_id     INTEGER   NOT NULL REFERENCES service(id) ON DELETE CASCADE,
    team_id        INTEGER   NOT NULL REFERENCES team(id)    ON DELETE CASCADE,
    priority_order SMALLINT  NOT NULL DEFAULT 100,
    is_active      BOOLEAN   NOT NULL DEFAULT TRUE,
    UNIQUE (service_id, team_id)
);
COMMENT ON TABLE routing_rule IS 'Правила автоматической маршрутизации заявок на группы';
CREATE INDEX idx_routing_active ON routing_rule(is_active, priority_order);

CREATE TABLE field_definition (
    id          SERIAL       PRIMARY KEY,
    code        VARCHAR(64)  NOT NULL UNIQUE,
    label       VARCHAR(128) NOT NULL,
    field_type  VARCHAR(16)  NOT NULL
                CHECK (field_type IN ('text','textarea','number','date','select','checkbox')),
    options     JSONB,
    is_required BOOLEAN      NOT NULL DEFAULT FALSE,
    order_num   SMALLINT     NOT NULL DEFAULT 100,
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE field_definition IS 'Описания пользовательских полей карточки заявки (low-code)';
CREATE INDEX idx_field_def_active ON field_definition(is_active, order_num);

-- =============================================================================
-- 6. АУДИТ
-- =============================================================================

CREATE TABLE audit_log (
    id          BIGSERIAL    PRIMARY KEY,
    actor_id    INTEGER               REFERENCES employee(id) ON DELETE SET NULL,
    action      VARCHAR(64)  NOT NULL,
    entity_type VARCHAR(64)  NOT NULL,
    entity_id   BIGINT,
    payload     JSONB,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE audit_log IS 'Журнал значимых действий пользователей и системы';
CREATE INDEX idx_audit_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_actor  ON audit_log(actor_id, created_at DESC);

-- =============================================================================
-- 7. ИСХОДНОЕ НАПОЛНЕНИЕ (seed)
-- =============================================================================

INSERT INTO role (code, name) VALUES
    ('admin',    'Администратор'),
    ('manager',  'Менеджер'),
    ('operator', 'Оператор'),
    ('executor', 'Исполнитель'),
    ('client',   'Клиент');

INSERT INTO status (code, name, order_num, is_terminal) VALUES
    ('new',         'Новая',           10, FALSE),
    ('in_progress', 'В работе',        20, FALSE),
    ('on_hold',     'Приостановлена',  30, FALSE),
    ('review',      'На проверке',     40, FALSE),
    ('done',        'Выполнена',       50, TRUE),
    ('cancelled',   'Отменена',        60, TRUE);

INSERT INTO priority (code, name, sla_hours) VALUES
    ('low',      'Низкий',     72),
    ('medium',   'Средний',    24),
    ('high',     'Высокий',     8),
    ('critical', 'Критический', 4);

-- Базовые услуги (пример для условной сервисной компании)
INSERT INTO service (name, default_duration_hours) VALUES
    ('Консультация',        2),
    ('Настройка ПО',        4),
    ('Ремонт оборудования', 8),
    ('Сетевые работы',      6);

-- Базовые группы исполнителей
INSERT INTO team (name) VALUES
    ('Поддержка 1-й линии'),
    ('Технические специалисты'),
    ('Сетевые инженеры');

COMMIT;

-- =============================================================================
-- 8. ПОЛЕЗНЫЕ ПРЕДСТАВЛЕНИЯ ДЛЯ ОТЧЁТНОСТИ (ФТ-4)
-- =============================================================================

-- Текущая загрузка исполнителей
CREATE OR REPLACE VIEW v_executor_load AS
SELECT
    e.id              AS employee_id,
    e.full_name,
    COUNT(r.id) FILTER (WHERE NOT s.is_terminal) AS open_count,
    COUNT(r.id) FILTER (WHERE r.due_date < NOW() AND NOT s.is_terminal) AS overdue_count
FROM employee e
LEFT JOIN request r ON r.assignee_id = e.id
LEFT JOIN status  s ON s.id = r.status_id
WHERE e.is_active
GROUP BY e.id, e.full_name;

-- Среднее время решения заявки за период (в часах)
CREATE OR REPLACE VIEW v_avg_resolution_time AS
SELECT
    DATE_TRUNC('day', r.closed_at) AS day,
    COUNT(*)                       AS closed_count,
    ROUND(AVG(EXTRACT(EPOCH FROM (r.closed_at - r.created_at)) / 3600)::numeric, 2)
                                   AS avg_hours
FROM request r
JOIN status s ON s.id = r.status_id
WHERE s.is_terminal AND r.closed_at IS NOT NULL
GROUP BY 1
ORDER BY 1 DESC;

-- Сводка по статусам и категориям
CREATE OR REPLACE VIEW v_request_summary AS
SELECT
    s.name      AS status_name,
    sv.name     AS service_name,
    p.name      AS priority_name,
    COUNT(*)    AS cnt
FROM request r
JOIN status   s  ON s.id  = r.status_id
JOIN service  sv ON sv.id = r.service_id
JOIN priority p  ON p.id  = r.priority_id
GROUP BY 1,2,3;
