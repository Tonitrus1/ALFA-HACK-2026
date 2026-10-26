# Модель данных и ограничения

Проектная модель, не готовая миграция. Схемы HTTP отдельно в contracts/.

## Session

Владелец: access. Поля: sessionId, actorRef, companyId, contextVersion, expiresAt.

Ограничения: contextVersion positive; rotate on login/company switch; role recheck.

## Application

Владелец: applications. Поля: applicationId, companyId, productId, productVersion, version, status, terms.

Ограничения: unique(companyId,applicationId); optimistic version; no patch after submit.

## SubmissionSnapshot

Владелец: applications. Поля: snapshotId, applicationId, version, packageDigest, createdAt.

Ограничения: immutable; unique application submission version.

## FinancialStatement

Владелец: applications. Поля: applicationId/requestId, statementVersion, containerVersion, period, values, confirmed.

Ограничения: eight field names; input change invalidates confirmation.

## FinancialSnapshot

Владелец: applications. Поля: financialSnapshotId, statementVersion, statementDigest, values, provenance.

Ограничения: immutable; company/application bound; exact objectVersion sources.

## InformationRequest

Владелец: journey. Поля: requestId, caseId, requestVersion, state, items.

Ограничения: one OPEN per case in MVP; addressed item allowlist.

## InformationDraft

Владелец: applications. Поля: requestId, draftVersion, financialStatementVersion, documentReferences.

Ограничения: CAS with requestVersion; unchanged unrequested financial fields.

## Consent

Владелец: consents. Поля: consentId, subjectRef, purpose, textVersion, actorRef, grantedAt, revokedAt.

Ограничения: no implicit delegation; expiry/revocation checked before command.

## Document

Владелец: documents. Поля: documentId, applicationId, companyId, objectVersion, sha256, state.

Ограничения: only CLEAN byte versions accepted; metadata version distinct.

## DocumentJob

Владелец: documents. Поля: jobId, generation, leaseTokenDigest, workerId, leaseExpiresAt, objectVersion, state.

Ограничения: compare generation and lease identity; retry bounded.

## CommandOperation

Владелец: journey. Поля: operationId, actorRef, companyId, commandType, clientKey, bodyDigest, state, result.

Ограничения: unique(actorRef,companyId,commandType,clientKey); result retained7days.

## Outbox

Владелец: journey. Поля: eventId, aggregateId, aggregateVersion, payload, state, nextAttemptAt.

Ограничения: committed with business effect; SKIP LOCKED delivery.

## Inbox

Владелец: integration. Поля: consumer, eventId, processedAt.

Ограничения: unique(consumer,eventId), atomic with handler effect.

## BankCase

Владелец: integration. Поля: caseId, externalRequestId, caseVersion, status, policyVersion.

Ограничения: simulator owns decision; command result unique externalRequestId.

## Offer

Владелец: integration. Поля: offerId, caseId, version, amount, termMonths, validUntil, status.

Ограничения: CAS acceptance/expiry/withdraw; full terms required.

## WorkspaceProjection

Владелец: workspace. Поля: applicationId, caseVersion, viewVersion, nextAction, updatedAt.

Ограничения: full normalized stream, gap=>snapshot.

## StreamEvent

Владелец: workspace. Поля: cursor, companyId, resourceRef, createdAt.

Ограничения: persisted cursor; authorized replay and barrier.

## FeatureSnapshot

Владелец: ml. Поля: featureSnapshotId, financialSnapshotId, snapshotDigest, features, asOf.

Ограничения: immutable; source availableAt<=asOf; missing mask matches nulls.

## InferenceRecord

Владелец: ml. Поля: requestId, bundleDigest, featureSnapshotDigest, output, createdAt.

Ограничения: durable before score response; idempotent same request/body.

## ReleaseBundle

Владелец: ml. Поля: releaseId, bundleDigest, artifactDigests, evaluationDigest, approvedBy.

Ограничения: no runtime download; reviewer distinct from author.

## KnowledgeVersion

Владелец: kb. Поля: documentId, documentVersion, audience, status, effectiveUntil, digest.

Ограничения: PUBLISHED gate; revoke never undone by model rollback.

## KBEpoch

Владелец: kb. Поля: scope, epoch.

Ограничения: increment in revoke transaction; final publication check.

## AssistantMessage

Владелец: kb. Поля: messageId, companyId, subjectRef, conversationId, sourceRefs, kbEpoch, answer.

Ограничения: authorised read; revoked source hides response; retention7days demo.

## RecommendationExposure

Владелец: workspace. Поля: exposureId, companyId, subjectRef, scope, candidateIds, bundleDigest.

Ограничения: permitted item IDs only; immutable assigned order.

## RecommendationFeedback

Владелец: workspace. Поля: clientEventId, exposureId, itemId, action, occurredAt.

Ограничения: dedup by actor/company/clientEventId; validate event time/TTL.


## Дополнение для ML-ленты

Канонический JSON расширен сущностями FeedPreferences, FeedSelection и FeedCardState. Профиль, последняя реакция и подтверждённые просмотры относятся к `(subjectRef, companyId)`, состояние карточки — дополнительно к стабильному contentId. Exposure хранит фактически выданные IDs/версии, а не разрешает feedback на весь результат ранжирования. События дедуплицируются по пользователю, компании и clientEventId; последняя принятая сервером реакция заменяет прежнюю. Cursor ссылается на сохранённую порцию; повтор сохраняет порядок с исключением скрытых без замены. Это дизайн хранения для backend, не готовые таблицы или миграции. Подробные правила и исполняемые примеры — [в передаче ленты](../../feed-integration.md).


## Сохранённые полезные карточки

FeedSavedState принадлежит workspace и хранит savedVersion (изначально 0) и снимки страниц по `(subjectRef, companyId)`. Изменение состава/порядка полезного и увеличение savedVersion выполняются в одной транзакции с принятием реакции. Повтор HELPFUL, VIEW и CLICK версию не меняют. FeedCardState хранит helpfulAcceptedSequence для сортировки по последнему действительному переходу в HELPFUL; userReaction в ответе — последняя принятая реакция или null.

Cursor полезного связан с владельцем, savedVersion и версией/digest каталога. Изменение сохранений или каталога даёт FEED_SAVED_EXPIRED. Для выданной сохранённой страницы создаётся отдельный RecommendationExposure с source=SAVED; он разрешает feedback только на выданные ID и не меняет VIEW или issued обычной подборки. Это контракт хранения, реализация и миграции остаются задачей backend.
