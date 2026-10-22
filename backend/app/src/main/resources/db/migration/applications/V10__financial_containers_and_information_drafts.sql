-- Финансовая форма как контейнер: исходная анкета (container_id = application_id) или черновик ответа на RFI
-- (container_id = request_id). Нумерация statement_version сквозная по заявке, поэтому provenance и снимки
-- остаются уникальными по (application_id, statement_version).
ALTER TABLE applications.financial_statement ADD COLUMN container_id text;
UPDATE applications.financial_statement SET container_id = application_id;
ALTER TABLE applications.financial_statement ALTER COLUMN container_id SET NOT NULL;
ALTER TABLE applications.financial_statement DROP CONSTRAINT financial_statement_pkey;
ALTER TABLE applications.financial_statement ADD PRIMARY KEY (container_id);
CREATE INDEX financial_statement_application_idx ON applications.financial_statement (application_id);

-- Черновик ответа на запрос банка (data-model: InformationDraft).
CREATE TABLE applications.information_draft (
    request_id                text        PRIMARY KEY,
    application_id            text        NOT NULL REFERENCES applications.application (application_id),
    company_id                text        NOT NULL,
    request_version           bigint      NOT NULL,
    draft_version             bigint      NOT NULL DEFAULT 1 CHECK (draft_version > 0),
    requirements_version      bigint      NOT NULL,
    base_statement_version    bigint      NOT NULL,
    requested_fields          text[]      NOT NULL,
    state                     text        NOT NULL CHECK (state IN ('EDITING', 'SUBMITTED')),
    created_at                timestamptz NOT NULL,
    updated_at                timestamptz NOT NULL
);
