CREATE SCHEMA ml;
CREATE TABLE ml.features(id text PRIMARY KEY,identity text UNIQUE NOT NULL,input_hash text NOT NULL,payload jsonb NOT NULL);
CREATE TABLE ml.inferences(id text PRIMARY KEY,request_id text UNIQUE NOT NULL,input_hash text NOT NULL,payload jsonb NOT NULL);
CREATE FUNCTION ml.prevent_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable ML record'; END; $$;
CREATE TRIGGER immutable_feature BEFORE UPDATE OR DELETE ON ml.features FOR EACH ROW EXECUTE FUNCTION ml.prevent_mutation();
CREATE TRIGGER immutable_inference BEFORE UPDATE OR DELETE ON ml.inferences FOR EACH ROW EXECUTE FUNCTION ml.prevent_mutation();
GRANT USAGE ON SCHEMA ml TO ml_runtime;
GRANT SELECT,INSERT ON ALL TABLES IN SCHEMA ml TO ml_runtime;
