-- Bind each feedback event to one stable HTTP command key as required by public OpenAPI.
ALTER TABLE workspace.feed_event ADD COLUMN client_key text;
UPDATE workspace.feed_event SET client_key=event_id;
ALTER TABLE workspace.feed_event ALTER COLUMN client_key SET NOT NULL;
ALTER TABLE workspace.feed_event ADD CONSTRAINT feed_event_client_key UNIQUE(actor_id,company_id,client_key);
