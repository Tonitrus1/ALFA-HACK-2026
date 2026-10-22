package ru.alfahack.credit.journey.application;

import java.time.Instant;

/** Долговечная команда (data-model: CommandOperation). */
public record OperationView(
        String operationId,
        String actorId,
        String companyId,
        String commandType,
        String clientKey,
        String bodyDigest,
        String applicationId,
        String resourceId,
        String state,
        String resultCode,
        String safeMessage,
        Instant createdAt,
        Instant updatedAt) {
}
