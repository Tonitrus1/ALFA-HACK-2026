-- Applications: черновики заявок и неизменяемые пакеты отправки (data-model: Application, SubmissionSnapshot).
CREATE TABLE applications.application (
    application_id                       text        PRIMARY KEY,
    company_id                           text        NOT NULL,
    product_id                           text        NOT NULL,
    product_version                      bigint      NOT NULL CHECK (product_version > 0),
    status                               text        NOT NULL,
    version                              bigint      NOT NULL DEFAULT 1 CHECK (version > 0),
    purpose                              text        NOT NULL,
    amount_minor                         bigint      NOT NULL CHECK (amount_minor >= 0),
    term_months                          integer     NOT NULL CHECK (term_months > 0),
    business_annual_revenue_minor        bigint      CHECK (business_annual_revenue_minor >= 0),
    business_annual_expenses_minor       bigint      CHECK (business_annual_expenses_minor >= 0),
    business_current_debt_minor          bigint      CHECK (business_current_debt_minor >= 0),
    business_age_months                  bigint      CHECK (business_age_months >= 0),
    business_activity_description        text,
    business_source_confirmation_version text,
    financial_statement_version          bigint,
    financial_snapshot_id                text,
    created_by                           text        NOT NULL,
    -- Повтор синхронного create с тем же ключом возвращает тот же ресурс.
    create_key                           text        NOT NULL,
    create_body_digest                   text        NOT NULL,
    created_at                           timestamptz NOT NULL,
    updated_at                           timestamptz NOT NULL,
    UNIQUE (company_id, application_id),
    UNIQUE (created_by, company_id, create_key)
);

CREATE INDEX application_company_updated_idx
    ON applications.application (company_id, updated_at DESC, application_id);

CREATE TABLE applications.submission_snapshot (
    snapshot_id                 text        PRIMARY KEY,
    application_id              text        NOT NULL REFERENCES applications.application (application_id),
    version                     bigint      NOT NULL CHECK (version > 0),
    package                     jsonb       NOT NULL,
    package_digest              text        NOT NULL,
    created_at                  timestamptz NOT NULL,
    UNIQUE (application_id, version)
);

CREATE FUNCTION applications.reject_snapshot_change() RETURNS trigger
    LANGUAGE plpgsql AS
$$
BEGIN
    RAISE EXCEPTION 'submission_snapshot is immutable';
END;
$$;

CREATE TRIGGER submission_snapshot_immutable
    BEFORE UPDATE OR DELETE ON applications.submission_snapshot
    FOR EACH ROW EXECUTE FUNCTION applications.reject_snapshot_change();
