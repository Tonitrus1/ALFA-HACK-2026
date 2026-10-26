# Физические таблицы из миграций

Автоматический inventory первоначальных CREATE TABLE. Последующие ALTER TABLE сохраняются в исходных миграциях и учитываются приложением. Это перечень физических объектов, а не ERD всех логических связей.

| База | Таблица | Исходная миграция |
|---|---|---|
| Business PostgreSQL | `access.credential` | [V20__password_credentials.sql](../../backend/app/src/main/resources/db/migration/access/V20__password_credentials.sql) |
| Business PostgreSQL | `access.actor` | [V2__access_actors_companies_sessions.sql](../../backend/app/src/main/resources/db/migration/access/V2__access_actors_companies_sessions.sql) |
| Business PostgreSQL | `access.company` | [V2__access_actors_companies_sessions.sql](../../backend/app/src/main/resources/db/migration/access/V2__access_actors_companies_sessions.sql) |
| Business PostgreSQL | `access.company_membership` | [V2__access_actors_companies_sessions.sql](../../backend/app/src/main/resources/db/migration/access/V2__access_actors_companies_sessions.sql) |
| Business PostgreSQL | `access.session` | [V2__access_actors_companies_sessions.sql](../../backend/app/src/main/resources/db/migration/access/V2__access_actors_companies_sessions.sql) |
| Business PostgreSQL | `applications.information_draft` | [V10__financial_containers_and_information_drafts.sql](../../backend/app/src/main/resources/db/migration/applications/V10__financial_containers_and_information_drafts.sql) |
| Business PostgreSQL | `applications.application` | [V4__applications_drafts_and_snapshots.sql](../../backend/app/src/main/resources/db/migration/applications/V4__applications_drafts_and_snapshots.sql) |
| Business PostgreSQL | `applications.submission_snapshot` | [V4__applications_drafts_and_snapshots.sql](../../backend/app/src/main/resources/db/migration/applications/V4__applications_drafts_and_snapshots.sql) |
| Business PostgreSQL | `applications.financial_statement` | [V7__financial_statements.sql](../../backend/app/src/main/resources/db/migration/applications/V7__financial_statements.sql) |
| Business PostgreSQL | `applications.financial_provenance` | [V7__financial_statements.sql](../../backend/app/src/main/resources/db/migration/applications/V7__financial_statements.sql) |
| Business PostgreSQL | `applications.financial_snapshot` | [V7__financial_statements.sql](../../backend/app/src/main/resources/db/migration/applications/V7__financial_statements.sql) |
| Business PostgreSQL | `applications.request_key` | [V7__financial_statements.sql](../../backend/app/src/main/resources/db/migration/applications/V7__financial_statements.sql) |
| Business PostgreSQL | `assistant.conversation` | [V19__assistant_sessions.sql](../../backend/app/src/main/resources/db/migration/assistant/V19__assistant_sessions.sql) |
| Business PostgreSQL | `catalog.product` | [V3__catalog_products.sql](../../backend/app/src/main/resources/db/migration/catalog/V3__catalog_products.sql) |
| Business PostgreSQL | `catalog.document_requirement` | [V8__catalog_document_requirements.sql](../../backend/app/src/main/resources/db/migration/catalog/V8__catalog_document_requirements.sql) |
| Business PostgreSQL | `documents.document` | [V9__documents_uploads_jobs.sql](../../backend/app/src/main/resources/db/migration/documents/V9__documents_uploads_jobs.sql) |
| Business PostgreSQL | `documents.upload` | [V9__documents_uploads_jobs.sql](../../backend/app/src/main/resources/db/migration/documents/V9__documents_uploads_jobs.sql) |
| Business PostgreSQL | `documents.download_grant` | [V9__documents_uploads_jobs.sql](../../backend/app/src/main/resources/db/migration/documents/V9__documents_uploads_jobs.sql) |
| Business PostgreSQL | `documents.document_job` | [V9__documents_uploads_jobs.sql](../../backend/app/src/main/resources/db/migration/documents/V9__documents_uploads_jobs.sql) |
| Business PostgreSQL | `documents.extraction` | [V9__documents_uploads_jobs.sql](../../backend/app/src/main/resources/db/migration/documents/V9__documents_uploads_jobs.sql) |
| Business PostgreSQL | `integration.decision` | [V12__integration_decisions_and_offers.sql](../../backend/app/src/main/resources/db/migration/integration/V12__integration_decisions_and_offers.sql) |
| Business PostgreSQL | `integration.offer` | [V12__integration_decisions_and_offers.sql](../../backend/app/src/main/resources/db/migration/integration/V12__integration_decisions_and_offers.sql) |
| Business PostgreSQL | `integration.review_task` | [V12__integration_decisions_and_offers.sql](../../backend/app/src/main/resources/db/migration/integration/V12__integration_decisions_and_offers.sql) |
| Business PostgreSQL | `integration.offer_command` | [V17__offer_commands.sql](../../backend/app/src/main/resources/db/migration/integration/V17__offer_commands.sql) |
| Business PostgreSQL | `integration.synthetic_reference` | [V18__synthetic_reference.sql](../../backend/app/src/main/resources/db/migration/integration/V18__synthetic_reference.sql) |
| Business PostgreSQL | `integration.fraud_attempt` | [V18__synthetic_reference.sql](../../backend/app/src/main/resources/db/migration/integration/V18__synthetic_reference.sql) |
| Business PostgreSQL | `integration.fraud_result` | [V18__synthetic_reference.sql](../../backend/app/src/main/resources/db/migration/integration/V18__synthetic_reference.sql) |
| Business PostgreSQL | `integration.inbox` | [V6__integration_bank_cases_and_inbox.sql](../../backend/app/src/main/resources/db/migration/integration/V6__integration_bank_cases_and_inbox.sql) |
| Business PostgreSQL | `integration.bank_case` | [V6__integration_bank_cases_and_inbox.sql](../../backend/app/src/main/resources/db/migration/integration/V6__integration_bank_cases_and_inbox.sql) |
| Business PostgreSQL | `journey.information_request` | [V11__journey_information_requests.sql](../../backend/app/src/main/resources/db/migration/journey/V11__journey_information_requests.sql) |
| Business PostgreSQL | `journey.command_operation` | [V5__journey_operations_and_outbox.sql](../../backend/app/src/main/resources/db/migration/journey/V5__journey_operations_and_outbox.sql) |
| Business PostgreSQL | `journey.outbox` | [V5__journey_operations_and_outbox.sql](../../backend/app/src/main/resources/db/migration/journey/V5__journey_operations_and_outbox.sql) |
| Business PostgreSQL | `ml.inference_record` | [V13__ml_inference_records.sql](../../backend/app/src/main/resources/db/migration/ml/V13__ml_inference_records.sql) |
| Business PostgreSQL | `workspace.feed_state` | [V14__feed.sql](../../backend/app/src/main/resources/db/migration/workspace/V14__feed.sql) |
| Business PostgreSQL | `workspace.feed_selection` | [V14__feed.sql](../../backend/app/src/main/resources/db/migration/workspace/V14__feed.sql) |
| Business PostgreSQL | `workspace.feed_page` | [V14__feed.sql](../../backend/app/src/main/resources/db/migration/workspace/V14__feed.sql) |
| Business PostgreSQL | `workspace.feed_event` | [V14__feed.sql](../../backend/app/src/main/resources/db/migration/workspace/V14__feed.sql) |
| Business PostgreSQL | `workspace.feed_reaction` | [V14__feed.sql](../../backend/app/src/main/resources/db/migration/workspace/V14__feed.sql) |
| ML PostgreSQL | `ml.features` | [V1__ml.sql](../../ml/migrations/V1__ml.sql) |
| ML PostgreSQL | `ml.inferences` | [V1__ml.sql](../../ml/migrations/V1__ml.sql) |
| ML PostgreSQL | `ml.bridge_call` | [V2__bridge.sql](../../ml/migrations/V2__bridge.sql) |
| ML PostgreSQL | `ml.fraud_features` | [V3__fraud.sql](../../ml/migrations/V3__fraud.sql) |
| ML PostgreSQL | `ml.fraud_inferences` | [V3__fraud.sql](../../ml/migrations/V3__fraud.sql) |
