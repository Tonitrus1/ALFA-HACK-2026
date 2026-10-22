-- Applications: финансовая форма DEMO Financial v1, provenance подтверждения и неизменяемые снимки
-- (data-model: FinancialStatement, FinancialSnapshot). Суммы — копейки; пропуск (NULL) отличается от нуля.
CREATE TABLE applications.financial_statement (
    application_id             text        PRIMARY KEY REFERENCES applications.application (application_id),
    statement_version          bigint      NOT NULL CHECK (statement_version > 0),
    period_start               date        NOT NULL,
    period_end                 date        NOT NULL,
    reporting_standard         text        NOT NULL CHECK (reporting_standard = 'DEMO'),
    currency                   text        NOT NULL CHECK (currency = 'RUB'),
    total_assets_minor         bigint      CHECK (total_assets_minor >= 0),
    total_liabilities_minor    bigint      CHECK (total_liabilities_minor >= 0),
    current_assets_minor       bigint      CHECK (current_assets_minor >= 0),
    current_liabilities_minor  bigint      CHECK (current_liabilities_minor >= 0),
    equity_minor               bigint,
    revenue_minor              bigint      CHECK (revenue_minor >= 0),
    net_profit_minor           bigint,
    ebit_minor                 bigint,
    source_document_references jsonb       NOT NULL DEFAULT '[]'::jsonb,
    confirmed                  boolean     NOT NULL DEFAULT false,
    updated_at                 timestamptz NOT NULL
);

-- Ровно одна provenance на поле подтверждённой версии; сервер формирует actor/time/source.
CREATE TABLE applications.financial_provenance (
    application_id    text        NOT NULL REFERENCES applications.application (application_id),
    statement_version bigint      NOT NULL,
    field             text        NOT NULL CHECK (field IN (
                          'totalAssetsMinor', 'totalLiabilitiesMinor', 'currentAssetsMinor', 'currentLiabilitiesMinor',
                          'equityMinor', 'revenueMinor', 'netProfitMinor', 'ebitMinor')),
    source_type       text        NOT NULL CHECK (source_type IN ('MANUAL', 'OCR')),
    confirmed_by      text        NOT NULL,
    confirmed_at      timestamptz NOT NULL,
    extraction_id     text,
    object_version    text,
    PRIMARY KEY (application_id, statement_version, field),
    CHECK (source_type <> 'OCR' OR (extraction_id IS NOT NULL AND object_version IS NOT NULL))
);

CREATE TABLE applications.financial_snapshot (
    financial_snapshot_id text        PRIMARY KEY,
    application_id        text        NOT NULL REFERENCES applications.application (application_id),
    company_id            text        NOT NULL,
    statement_version     bigint      NOT NULL,
    statement_digest      text        NOT NULL,
    statement             jsonb       NOT NULL,
    provenance            jsonb       NOT NULL,
    created_at            timestamptz NOT NULL,
    UNIQUE (application_id, statement_version)
);

CREATE TRIGGER financial_snapshot_immutable
    BEFORE UPDATE OR DELETE ON applications.financial_snapshot
    FOR EACH ROW EXECUTE FUNCTION applications.reject_snapshot_change();

-- Идемпотентность синхронных изменений формы (PUT/confirm): повтор возвращает текущее представление.
CREATE TABLE applications.request_key (
    actor_id       text        NOT NULL,
    company_id     text        NOT NULL,
    scope          text        NOT NULL,
    client_key     text        NOT NULL,
    body_digest    text        NOT NULL,
    application_id text        NOT NULL,
    created_at     timestamptz NOT NULL,
    PRIMARY KEY (actor_id, company_id, scope, client_key)
);
