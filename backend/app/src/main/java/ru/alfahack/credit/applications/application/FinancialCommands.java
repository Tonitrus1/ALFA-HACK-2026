package ru.alfahack.credit.applications.application;

import java.time.LocalDate;
import java.util.List;

public final class FinancialCommands {

    private FinancialCommands() {
    }

    public record Save(
            LocalDate periodStart,
            LocalDate periodEnd,
            String reportingStandard,
            String currency,
            FinancialValues values,
            List<ApplicationCommands.DocumentReference> sourceDocumentReferences) {
    }

    public record Confirm(
            long expectedStatementVersion,
            List<String> confirmedFieldNames,
            List<ApplicationCommands.DocumentReference> documentReferences) {
    }
}
