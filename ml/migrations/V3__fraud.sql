CREATE TABLE ml.fraud_features(id text PRIMARY KEY,identity text UNIQUE NOT NULL,input_hash text NOT NULL,payload jsonb NOT NULL);
CREATE TABLE ml.fraud_inferences(id text PRIMARY KEY,request_id text UNIQUE NOT NULL,input_hash text NOT NULL,payload jsonb NOT NULL);
CREATE TRIGGER immutable_fraud_feature BEFORE UPDATE OR DELETE ON ml.fraud_features FOR EACH ROW EXECUTE FUNCTION ml.prevent_mutation();
CREATE TRIGGER immutable_fraud_inference BEFORE UPDATE OR DELETE ON ml.fraud_inferences FOR EACH ROW EXECUTE FUNCTION ml.prevent_mutation();
GRANT SELECT,INSERT ON ml.fraud_features,ml.fraud_inferences TO ml_runtime;
