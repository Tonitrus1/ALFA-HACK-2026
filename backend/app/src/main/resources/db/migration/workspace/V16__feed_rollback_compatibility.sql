-- Preserve pre-V15 writers during a code rollback: their stable body event ID is the legacy key.
-- New writers always supply the explicit HTTP key; neither event IDs nor payloads are changed.
CREATE FUNCTION workspace.feed_legacy_command_key() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.client_key IS NULL THEN NEW.client_key := NEW.event_id; END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER feed_legacy_command_key BEFORE INSERT ON workspace.feed_event
    FOR EACH ROW EXECUTE FUNCTION workspace.feed_legacy_command_key();
