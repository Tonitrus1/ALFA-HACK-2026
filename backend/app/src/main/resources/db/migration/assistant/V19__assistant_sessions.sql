CREATE SCHEMA IF NOT EXISTS assistant;
-- Tokens stay server-side, scoped to the authenticated browser session and selected company.
CREATE TABLE assistant.conversation (
    owner_hash text NOT NULL,
    company_id text NOT NULL,
    conversation_id text NOT NULL,
    remote_id text NOT NULL,
    remote_token text NOT NULL,
    expires_at timestamptz NOT NULL,
    PRIMARY KEY (owner_hash, company_id, conversation_id)
);
