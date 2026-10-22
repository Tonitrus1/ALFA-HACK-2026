package ru.alfahack.credit.applications.application;

import java.time.Instant;
import java.util.List;
import java.util.Set;

/** Входные данные команд applications после разбора HTTP. */
public final class ApplicationCommands {

    private ApplicationCommands() {
    }

    public record Create(
            String companyId, String productId, long productVersion,
            String purpose, long amountMinor, int termMonths, String urgency) {
    }

    /** Частичное обновление: null — поле не меняется; clearFields — явная очистка полей business. */
    public record Patch(
            String purpose, Long amountMinor, Integer termMonths, BusinessData business, Set<String> clearFields) {
    }

    public record DocumentReference(String documentId, long documentVersion, String objectVersion) {
    }

    public record Submit(
            long expectedVersion,
            List<String> consentRecordIds,
            List<String> documentIds,
            List<DocumentReference> documentReferences,
            long requirementsVersion,
            long financialStatementVersion) {
    }

    public record Receipt(String operationId, String applicationId, Instant acceptedAt) {
    }
}
