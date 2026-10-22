package ru.alfahack.credit.applications.application;

import java.util.List;
import java.util.Optional;

import org.springframework.stereotype.Component;

import ru.alfahack.credit.catalog.application.ProductView;

/**
 * Реализация до P08/P10/согласий: финансовой формы ещё нет — подтверждения нет (отказ);
 * документов и согласий ещё нет — любая непустая ссылка не может быть проверена (отказ).
 * Требований согласий в каталоге пока нет, поэтому пустой список согласий допустим.
 */
@Component
class PendingSubmissionPrerequisites implements SubmissionPrerequisites {

    @Override
    public Optional<String> confirmedFinancialSnapshot(ApplicationView application, long financialStatementVersion) {
        return Optional.empty();
    }

    @Override
    public boolean documentsClean(ApplicationView application, List<ApplicationCommands.DocumentReference> references) {
        return references.isEmpty();
    }

    @Override
    public boolean consentsValid(ApplicationView application, ProductView product, List<String> consentRecordIds) {
        return consentRecordIds.isEmpty();
    }
}
