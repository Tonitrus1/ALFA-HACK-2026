-- Explicit maintenance operation, never a startup migration. Targets only companies A and B.
BEGIN;
SET LOCAL lock_timeout = '15s';
CREATE TEMP TABLE reset_companies(company_id text PRIMARY KEY) ON COMMIT DROP;
INSERT INTO reset_companies VALUES ('company-a'), ('company-b');
CREATE TEMP TABLE reset_apps ON COMMIT DROP AS
    SELECT application_id FROM applications.application WHERE company_id IN (SELECT company_id FROM reset_companies);
CREATE TEMP TABLE reset_docs ON COMMIT DROP AS
    SELECT document_id FROM documents.document WHERE company_id IN (SELECT company_id FROM reset_companies)
       OR application_id IN (SELECT application_id FROM reset_apps);

-- Snapshot immutability remains enforced during normal application use.
ALTER TABLE applications.submission_snapshot DISABLE TRIGGER submission_snapshot_immutable;
ALTER TABLE applications.financial_snapshot DISABLE TRIGGER financial_snapshot_immutable;
ALTER TABLE integration.fraud_attempt DISABLE TRIGGER immutable_fraud_attempt;
ALTER TABLE integration.fraud_result DISABLE TRIGGER immutable_fraud_result;

DELETE FROM integration.fraud_result WHERE attempt_id IN (
    SELECT attempt_id FROM integration.fraud_attempt WHERE company_id IN (SELECT company_id FROM reset_companies)
       OR application_id IN (SELECT application_id FROM reset_apps));
DELETE FROM integration.fraud_attempt WHERE company_id IN (SELECT company_id FROM reset_companies)
    OR application_id IN (SELECT application_id FROM reset_apps);
DELETE FROM integration.offer_command WHERE company_id IN (SELECT company_id FROM reset_companies);
DELETE FROM integration.offer WHERE company_id IN (SELECT company_id FROM reset_companies)
    OR application_id IN (SELECT application_id FROM reset_apps);
DELETE FROM integration.review_task WHERE case_id IN (
    SELECT case_id FROM integration.bank_case WHERE company_id IN (SELECT company_id FROM reset_companies));
DELETE FROM integration.decision WHERE application_id IN (SELECT application_id FROM reset_apps);
DELETE FROM integration.bank_case WHERE company_id IN (SELECT company_id FROM reset_companies);
DELETE FROM integration.inbox WHERE event_id IN (
    SELECT event_id FROM journey.outbox WHERE application_id IN (SELECT application_id FROM reset_apps));
DELETE FROM journey.outbox WHERE application_id IN (SELECT application_id FROM reset_apps);
DELETE FROM journey.command_operation WHERE company_id IN (SELECT company_id FROM reset_companies);
DELETE FROM journey.information_request WHERE company_id IN (SELECT company_id FROM reset_companies);
DELETE FROM ml.inference_record WHERE application_id IN (SELECT application_id FROM reset_apps);
DELETE FROM documents.download_grant WHERE document_id IN (SELECT document_id FROM reset_docs);
DELETE FROM documents.upload WHERE document_id IN (SELECT document_id FROM reset_docs);
DELETE FROM documents.document_job WHERE document_id IN (SELECT document_id FROM reset_docs);
DELETE FROM documents.extraction WHERE document_id IN (SELECT document_id FROM reset_docs);
DELETE FROM documents.document WHERE document_id IN (SELECT document_id FROM reset_docs);
DELETE FROM applications.information_draft WHERE application_id IN (SELECT application_id FROM reset_apps);
DELETE FROM applications.financial_provenance WHERE application_id IN (SELECT application_id FROM reset_apps);
DELETE FROM applications.financial_snapshot WHERE application_id IN (SELECT application_id FROM reset_apps);
DELETE FROM applications.financial_statement WHERE application_id IN (SELECT application_id FROM reset_apps);
DELETE FROM applications.submission_snapshot WHERE application_id IN (SELECT application_id FROM reset_apps);
DELETE FROM applications.request_key WHERE company_id IN (SELECT company_id FROM reset_companies);
DELETE FROM applications.application WHERE application_id IN (SELECT application_id FROM reset_apps);
DELETE FROM workspace.feed_page WHERE company_id IN (SELECT company_id FROM reset_companies);
DELETE FROM workspace.feed_selection WHERE company_id IN (SELECT company_id FROM reset_companies);
DELETE FROM workspace.feed_event WHERE company_id IN (SELECT company_id FROM reset_companies);
DELETE FROM workspace.feed_reaction WHERE company_id IN (SELECT company_id FROM reset_companies);
DELETE FROM workspace.feed_state WHERE company_id IN (SELECT company_id FROM reset_companies);
DELETE FROM assistant.conversation WHERE company_id IN (SELECT company_id FROM reset_companies);
DELETE FROM access.session WHERE selected_company_id IN (SELECT company_id FROM reset_companies)
    OR actor_id IN (SELECT actor_id FROM access.company_membership WHERE company_id IN (SELECT company_id FROM reset_companies));
UPDATE access.actor SET auth_epoch=auth_epoch+1 WHERE actor_id IN (
    SELECT actor_id FROM access.company_membership WHERE company_id IN (SELECT company_id FROM reset_companies));

ALTER TABLE applications.submission_snapshot ENABLE TRIGGER submission_snapshot_immutable;
ALTER TABLE applications.financial_snapshot ENABLE TRIGGER financial_snapshot_immutable;
ALTER TABLE integration.fraud_attempt ENABLE TRIGGER immutable_fraud_attempt;
ALTER TABLE integration.fraud_result ENABLE TRIGGER immutable_fraud_result;
COMMIT;

SELECT company_id,
    (SELECT count(*) FROM applications.application a WHERE a.company_id=c.company_id) AS applications,
    (SELECT count(*) FROM documents.document d WHERE d.company_id=c.company_id) AS documents,
    (SELECT count(*) FROM assistant.conversation s WHERE s.company_id=c.company_id) AS conversations,
    (SELECT count(*) FROM workspace.feed_state f WHERE f.company_id=c.company_id) AS feed_settings,
    (SELECT count(*) FROM workspace.feed_reaction f WHERE f.company_id=c.company_id) AS feed_reactions
FROM access.company c WHERE company_id IN ('company-a','company-b') ORDER BY company_id;
