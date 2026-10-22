-- Journey: запросы банка о дополнительных сведениях (data-model: InformationRequest). Один OPEN на заявку.
CREATE TABLE journey.information_request (
    request_id     text        PRIMARY KEY,
    application_id text        NOT NULL,
    company_id     text        NOT NULL,
    case_id        text        NOT NULL,
    version        bigint      NOT NULL DEFAULT 1 CHECK (version > 0),
    status         text        NOT NULL CHECK (status IN ('OPEN', 'RESPONDED', 'CLOSED', 'EXPIRED')),
    items          jsonb       NOT NULL,
    deadline       timestamptz,
    created_at     timestamptz NOT NULL,
    updated_at     timestamptz NOT NULL
);

CREATE UNIQUE INDEX information_request_one_open_idx
    ON journey.information_request (application_id) WHERE status IN ('OPEN', 'RESPONDED');

