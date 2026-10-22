package ru.alfahack.credit.applications.application;

import java.util.List;

/** Черновик ответа на RFI; requestedFields — запрошенные пути financialStatement.values.*. */
public record InformationDraftView(
        String requestId,
        String applicationId,
        String companyId,
        long requestVersion,
        long draftVersion,
        long requirementsVersion,
        long baseStatementVersion,
        List<String> requestedFields,
        String state) {

    public InformationDraftView {
        requestedFields = List.copyOf(requestedFields);
    }
}
