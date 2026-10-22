package ru.alfahack.credit.applications.application;

import java.util.List;

public final class InformationCommands {

    private InformationCommands() {
    }

    /** Поля amendment/explanation/documentReferences: null — не передано. */
    public record DraftPatch(
            long requestVersion, boolean hasAmendment, List<ApplicationCommands.DocumentReference> documentReferences,
            String explanation, long requirementsVersion) {
    }

    public record Response(
            long requestVersion, boolean hasAmendment, List<String> documentIds, String explanation,
            List<ApplicationCommands.DocumentReference> documentReferences, long requirementsVersion,
            long draftVersion, long financialStatementVersion) {
    }
}
