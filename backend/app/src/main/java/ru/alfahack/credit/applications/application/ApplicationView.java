package ru.alfahack.credit.applications.application;

import java.time.Instant;

/** Заявка: редактируемые условия, версия и состояние. */
public record ApplicationView(
        String applicationId,
        String companyId,
        String productId,
        long productVersion,
        String status,
        long version,
        String purpose,
        long amountMinor,
        int termMonths,
        BusinessData business,
        Long financialStatementVersion,
        String financialSnapshotId,
        String createdBy,
        String createKey,
        String createBodyDigest,
        Instant createdAt,
        Instant updatedAt) {
}
