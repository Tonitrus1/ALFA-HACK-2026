-- Documents: документы заявки, разрешения загрузки/скачивания, задания SCAN/EXTRACT с арендой, извлечения OCR.
CREATE TABLE documents.document (
    document_id          text        PRIMARY KEY,
    application_id       text        NOT NULL,
    company_id           text        NOT NULL,
    requirement_id       text        NOT NULL,
    requirements_version bigint      NOT NULL,
    document_type        text        NOT NULL,
    file_name            text        NOT NULL,
    declared_mime_type   text        NOT NULL,
    declared_size_bytes  bigint      NOT NULL CHECK (declared_size_bytes BETWEEN 1 AND 10485760),
    content_type         text,
    size_bytes           bigint,
    sha256               text,
    object_id            text,
    object_version       text,
    scan_state           text        NOT NULL CHECK (scan_state IN ('UPLOADING', 'QUARANTINED', 'CLEAN', 'REJECTED', 'DELETED')),
    extraction_state     text        NOT NULL CHECK (extraction_state IN ('NOT_REQUESTED', 'PENDING', 'READY', 'FAILED', 'CONFIRMED')),
    extraction_id        text,
    max_pages            integer     NOT NULL,
    replaces_document_id text,
    version              bigint      NOT NULL DEFAULT 1 CHECK (version > 0),
    created_by           text        NOT NULL,
    created_at           timestamptz NOT NULL,
    updated_at           timestamptz NOT NULL
);

CREATE INDEX document_application_idx ON documents.document (application_id, created_at, document_id);

CREATE TABLE documents.upload (
    upload_id          text        PRIMARY KEY,
    transfer_id        text        NOT NULL UNIQUE,
    document_id        text        NOT NULL REFERENCES documents.document (document_id),
    grant_hash         text        NOT NULL,
    session_hash       text        NOT NULL,
    actor_id           text        NOT NULL,
    company_id         text        NOT NULL,
    max_bytes          bigint      NOT NULL,
    state              text        NOT NULL CHECK (state IN ('PENDING', 'COMPLETED', 'CANCELLED')),
    version            bigint      NOT NULL DEFAULT 1,
    client_key         text        NOT NULL,
    body_digest        text        NOT NULL,
    expires_at         timestamptz NOT NULL,
    created_at         timestamptz NOT NULL,
    UNIQUE (actor_id, company_id, client_key)
);

CREATE TABLE documents.download_grant (
    transfer_id    text        PRIMARY KEY,
    grant_hash     text        NOT NULL,
    session_hash   text        NOT NULL,
    document_id    text        NOT NULL REFERENCES documents.document (document_id),
    object_version text        NOT NULL,
    expires_at     timestamptz NOT NULL,
    created_at     timestamptz NOT NULL
);

CREATE TABLE documents.document_job (
    job_id           text        PRIMARY KEY,
    document_id      text        NOT NULL REFERENCES documents.document (document_id),
    job_type         text        NOT NULL CHECK (job_type IN ('SCAN', 'EXTRACT')),
    object_version   text        NOT NULL,
    state            text        NOT NULL CHECK (state IN ('PENDING', 'LEASED', 'DONE', 'FAILED')),
    generation       bigint      NOT NULL DEFAULT 0,
    worker_id        text,
    lease_token_hash text,
    lease_until      timestamptz,
    attempts         integer     NOT NULL DEFAULT 0,
    next_attempt_at  timestamptz NOT NULL,
    last_error       text,
    created_at       timestamptz NOT NULL,
    updated_at       timestamptz NOT NULL,
    UNIQUE (document_id, job_type, object_version)
);

CREATE INDEX document_job_claim_idx ON documents.document_job (job_type, state, next_attempt_at);

CREATE TABLE documents.extraction (
    extraction_id    text        PRIMARY KEY,
    document_id      text        NOT NULL REFERENCES documents.document (document_id),
    document_version bigint      NOT NULL,
    object_version   text        NOT NULL,
    model_version    text        NOT NULL,
    status           text        NOT NULL CHECK (status IN ('READY', 'FAILED')),
    fields           jsonb       NOT NULL,
    created_at       timestamptz NOT NULL
);
