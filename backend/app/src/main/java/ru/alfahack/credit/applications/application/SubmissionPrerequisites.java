package ru.alfahack.credit.applications.application;

import java.util.List;
import java.util.Optional;

import ru.alfahack.credit.catalog.application.ProductView;

/**
 * Предусловия отправки, которыми владеют другие задачи: подтверждённые финансы (P08), CLEAN-документы (P10)
 * и согласия. Реализация обязана отказывать закрыто: неизвестное или непроверенное — не готово.
 */
public interface SubmissionPrerequisites {

    /** financialSnapshotId, созданный сервером из подтверждённой формы именно этой версии; иначе пусто. */
    Optional<String> confirmedFinancialSnapshot(ApplicationView application, long financialStatementVersion);

    boolean documentsClean(ApplicationView application, List<ApplicationCommands.DocumentReference> references);

    boolean consentsValid(ApplicationView application, ProductView product, List<String> consentRecordIds);
}
