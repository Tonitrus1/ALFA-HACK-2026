-- Integration: решения симулятора по demo-policy v1, предложения и очередь рассмотрения дел.
ALTER TABLE integration.bank_case ADD COLUMN financial_snapshot_id text;

CREATE TABLE integration.decision (
    decision_id         text        PRIMARY KEY,
    case_id             text        NOT NULL REFERENCES integration.bank_case (case_id),
    application_id      text        NOT NULL,
    case_version        bigint      NOT NULL,
    outcome             text        NOT NULL CHECK (outcome IN ('APPROVED', 'ALTERNATIVE', 'NEEDS_INFO', 'DECLINED', 'MANUAL')),
    public_explanation  text        NOT NULL,
    policy_version      text        NOT NULL,
    reason_codes        text[]      NOT NULL,
    risk_inference_id   text,
    risk_mode           text        NOT NULL CHECK (risk_mode IN ('MODEL', 'CONTRACT_DOUBLE', 'UNAVAILABLE', 'NOT_REQUIRED')),
    financial_snapshot_id text      NOT NULL,
    created_at          timestamptz NOT NULL,
    UNIQUE (case_id, case_version)
);

CREATE TABLE integration.offer (
    offer_id         text        PRIMARY KEY,
    decision_id      text        NOT NULL REFERENCES integration.decision (decision_id),
    application_id   text        NOT NULL,
    company_id       text        NOT NULL,
    version          bigint      NOT NULL DEFAULT 1,
    status           text        NOT NULL CHECK (status IN ('AVAILABLE', 'ACCEPTED', 'EXPIRED', 'WITHDRAWN')),
    amount_minor     bigint      NOT NULL CHECK (amount_minor > 0),
    term_months      integer     NOT NULL CHECK (term_months > 0),
    terms_disclosure text        NOT NULL,
    valid_until      timestamptz NOT NULL,
    created_at       timestamptz NOT NULL
);

CREATE INDEX offer_application_idx ON integration.offer (application_id);

-- Рассмотрение выполняет отдельный worker: внешний вызов risk не держит транзакцию доставки события.
CREATE TABLE integration.review_task (
    task_id         text        PRIMARY KEY,
    case_id         text        NOT NULL REFERENCES integration.bank_case (case_id),
    case_version    bigint      NOT NULL,
    state           text        NOT NULL CHECK (state IN ('PENDING', 'LEASED', 'DONE')),
    lease_until     timestamptz,
    created_at      timestamptz NOT NULL,
    updated_at      timestamptz NOT NULL,
    UNIQUE (case_id, case_version)
);
