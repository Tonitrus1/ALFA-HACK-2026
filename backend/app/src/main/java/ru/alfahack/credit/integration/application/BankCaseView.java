package ru.alfahack.credit.integration.application;

import java.time.Instant;

/** Банковское дело симулятора; caseVersion монотонно растёт. */
public record BankCaseView(
        String caseId,
        String applicationId,
        String companyId,
        String externalRequestId,
        long caseVersion,
        String status,
        Instant createdAt,
        Instant updatedAt,
        String financialSnapshotId) {
}
