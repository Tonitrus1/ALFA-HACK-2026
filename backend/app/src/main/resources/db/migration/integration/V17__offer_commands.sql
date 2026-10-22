-- New business commands; previous migrations and user data remain unchanged.
ALTER TABLE integration.offer DROP CONSTRAINT offer_status_check;
ALTER TABLE integration.offer ADD CONSTRAINT offer_status_check
 CHECK (status IN ('AVAILABLE','ACCEPTED','COMPLETED','EXPIRED','WITHDRAWN'));
CREATE TABLE integration.offer_command (
 actor_id text NOT NULL, company_id text NOT NULL, client_key text NOT NULL,
 fingerprint text NOT NULL, response jsonb NOT NULL, created_at timestamptz NOT NULL,
 PRIMARY KEY(actor_id,company_id,client_key)
);
