-- Independent immutable synthetic fixture, never derived from a user form.
CREATE TABLE integration.synthetic_reference (
 reference_id text PRIMARY KEY, company_id text NOT NULL, period_start date NOT NULL,
 version bigint NOT NULL, available_at timestamptz NOT NULL, record jsonb NOT NULL,
 UNIQUE(company_id,period_start,version)
);
CREATE FUNCTION integration.reject_proxy_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Immutable synthetic provenance'; END; $$;
CREATE TRIGGER immutable_synthetic_reference BEFORE UPDATE OR DELETE ON integration.synthetic_reference
 FOR EACH ROW EXECUTE FUNCTION integration.reject_proxy_mutation();
CREATE TABLE integration.fraud_attempt (
 attempt_id text PRIMARY KEY, company_id text NOT NULL, application_id text NOT NULL,
 case_version bigint NOT NULL, financial_snapshot_id text NOT NULL, financial_digest text NOT NULL,
 risk_inference_id text NOT NULL, reference_id text NOT NULL REFERENCES integration.synthetic_reference,
 reference_digest text NOT NULL, created_at timestamptz NOT NULL,
 UNIQUE(application_id,case_version)
);
CREATE TRIGGER immutable_fraud_attempt BEFORE UPDATE OR DELETE ON integration.fraud_attempt
 FOR EACH ROW EXECUTE FUNCTION integration.reject_proxy_mutation();
CREATE TABLE integration.fraud_result (
 attempt_id text PRIMARY KEY REFERENCES integration.fraud_attempt, inference_id text NOT NULL,
 result jsonb NOT NULL, created_at timestamptz NOT NULL
);
CREATE TRIGGER immutable_fraud_result BEFORE UPDATE OR DELETE ON integration.fraud_result
 FOR EACH ROW EXECUTE FUNCTION integration.reject_proxy_mutation();
