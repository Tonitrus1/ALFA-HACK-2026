-- Journey: долговечные команды с идемпотентностью и транзакционный outbox (data-model: CommandOperation, Outbox).
CREATE TABLE journey.command_operation (
    operation_id   text        PRIMARY KEY,
    actor_id       text        NOT NULL,
    company_id     text        NOT NULL,
    command_type   text        NOT NULL CHECK (command_type IN ('SUBMIT', 'RESPOND', 'WITHDRAW', 'ACCEPT')),
    client_key     text        NOT NULL,
    body_digest    text        NOT NULL,
    application_id text        NOT NULL,
    resource_id    text        NOT NULL,
    state          text        NOT NULL CHECK (state IN ('PENDING', 'SUCCEEDED', 'FAILED', 'RECONCILING')),
    result_code    text,
    safe_message   text,
    created_at     timestamptz NOT NULL,
    updated_at     timestamptz NOT NULL,
    UNIQUE (actor_id, company_id, command_type, client_key)
);

CREATE INDEX command_operation_actor_idx ON journey.command_operation (actor_id, company_id, created_at);

CREATE TABLE journey.outbox (
    event_id          uuid        PRIMARY KEY,
    event_type        text        NOT NULL,
    aggregate_id      text        NOT NULL,
    aggregate_version bigint      NOT NULL CHECK (aggregate_version > 0),
    application_id    text        NOT NULL,
    envelope          jsonb       NOT NULL,
    state             text        NOT NULL DEFAULT 'PENDING' CHECK (state IN ('PENDING', 'DELIVERED', 'FAILED')),
    attempts          integer     NOT NULL DEFAULT 0,
    next_attempt_at   timestamptz NOT NULL,
    lease_owner       text,
    lease_expires_at  timestamptz,
    last_error        text,
    created_at        timestamptz NOT NULL,
    delivered_at      timestamptz,
    UNIQUE (event_type, aggregate_id, aggregate_version)
);

CREATE INDEX outbox_state_next_attempt_idx ON journey.outbox (state, next_attempt_at);
