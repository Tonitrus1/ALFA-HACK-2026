package ru.alfahack.credit.applications.application;

import java.util.List;
import java.util.Optional;

import org.springframework.stereotype.Component;

import ru.alfahack.credit.catalog.application.ProductView;

/**
 * Финансы — подтверждённая форма точной версии, снимок создаётся в транзакции submit (P08).
 * Документы — через {@link DocumentReferenceGate}. Требований согласий в каталоге пока нет, поэтому
 * допустим пустой список; непустой не может быть проверен до модуля согласий и отклоняется.
 */
@Component
class DefaultSubmissionPrerequisites implements SubmissionPrerequisites {

    private final FinancialStatementService financials;
    private final DocumentReferenceGate documents;

    DefaultSubmissionPrerequisites(FinancialStatementService financials, DocumentReferenceGate documents) {
        this.financials = financials;
        this.documents = documents;
    }

    @Override
    public Optional<String> confirmedFinancialSnapshot(ApplicationView application, long financialStatementVersion) {
        return financials.snapshotForSubmit(application, financialStatementVersion);
    }

    @Override
    public boolean documentsClean(ApplicationView application, List<ApplicationCommands.DocumentReference> references) {
        return documents.allClean(application, references);
    }

    @Override
    public boolean consentsValid(ApplicationView application, ProductView product, List<String> consentRecordIds) {
        return consentRecordIds.isEmpty();
    }
}
