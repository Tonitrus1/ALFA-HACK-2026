-- Integration: банковский симулятор и inbox потребителей (data-model: BankCase, Inbox).
CREATE TABLE integration.inbox (
    consumer     text        NOT NULL,
    event_id     uuid        NOT NULL,
    processed_at timestamptz NOT NULL,
    PRIMARY KEY (consumer, event_id)
);

CREATE TABLE integration.bank_case (
    case_id             text        PRIMARY KEY,
    application_id      text        NOT NULL UNIQUE,
    company_id          text        NOT NULL,
    external_request_id text        NOT NULL UNIQUE,
    case_version        bigint      NOT NULL CHECK (case_version > 0),
    status              text        NOT NULL,
    policy_version      text,
    created_at          timestamptz NOT NULL,
    updated_at          timestamptz NOT NULL
);
