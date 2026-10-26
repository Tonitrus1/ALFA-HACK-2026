package ru.alfahack.credit.applications.application;

import java.time.Instant;
import java.time.LocalDate;
import java.util.List;

/** Финансовая форма заявки; containerVersion — версия заявки (её ETag). */
public record FinancialStatementView(
        String applicationId,
        long statementVersion,
        long containerVersion,
        LocalDate periodStart,
        LocalDate periodEnd,
        String reportingStandard,
        String currency,
        FinancialValues values,
        List<ApplicationCommands.DocumentReference> sourceDocumentReferences,
        boolean confirmed,
        List<FieldProvenance> provenance,
        Instant updatedAt) {

    public FinancialStatementView {
        sourceDocumentReferences = List.copyOf(sourceDocumentReferences);
        provenance = List.copyOf(provenance);
    }

    public record FieldProvenance(
            String field, String sourceType, String confirmedBy, Instant confirmedAt, String extractionId,
            String objectVersion) {
    }

    /** Содержимое формы без версий и подтверждения — для сравнения «было ли изменение». */
    public record Content(
            LocalDate periodStart,
            LocalDate periodEnd,
            String reportingStandard,
            String currency,
            FinancialValues values,
            List<ApplicationCommands.DocumentReference> sourceDocumentReferences) {

        public Content {
            sourceDocumentReferences = List.copyOf(sourceDocumentReferences);
        }
    }

    public Content content() {
        return new Content(periodStart, periodEnd, reportingStandard, currency, values, sourceDocumentReferences);
    }
}
