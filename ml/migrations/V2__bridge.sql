-- ML-owned journal. Backend Flyway tables remain in a separate database.
CREATE TABLE ml.bridge_call (
    call_key text PRIMARY KEY,
    input_hash text NOT NULL,
    request jsonb NOT NULL,
    response jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE FUNCTION ml.protect_bridge_call() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'immutable bridge call'; END IF;
    IF OLD.call_key <> NEW.call_key OR OLD.input_hash <> NEW.input_hash
       OR OLD.request <> NEW.request OR OLD.created_at <> NEW.created_at
       OR OLD.response IS NOT NULL OR NEW.response IS NULL THEN
        RAISE EXCEPTION 'immutable bridge input/result';
    END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER protect_bridge_call BEFORE UPDATE OR DELETE ON ml.bridge_call
    FOR EACH ROW EXECUTE FUNCTION ml.protect_bridge_call();
GRANT SELECT, INSERT, UPDATE ON ml.bridge_call TO ml_runtime;
