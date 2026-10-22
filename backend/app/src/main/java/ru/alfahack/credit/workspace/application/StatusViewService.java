package ru.alfahack.credit.workspace.application;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

import org.springframework.stereotype.Service;

import ru.alfahack.credit.access.application.AuthenticatedSession;
import ru.alfahack.credit.applications.application.ApplicationService;
import ru.alfahack.credit.applications.application.ApplicationView;
import ru.alfahack.credit.integration.application.BankCaseView;
import ru.alfahack.credit.integration.application.BankCases;
import ru.alfahack.credit.workspace.application.StatusViewModel.HistoryEvent;
import ru.alfahack.credit.workspace.application.StatusViewModel.NextAction;

/**
 * Статус собирается из заявки и банковского дела: банковский статус авторитетен, когда дело есть.
 * viewVersion = версия заявки + caseVersion — монотонна, пока монотонны обе последовательности.
 */
@Service
public class StatusViewService {

    private final ApplicationService applications;
    private final BankCases bankCases;

    public StatusViewService(ApplicationService applications, BankCases bankCases) {
        this.applications = applications;
        this.bankCases = bankCases;
    }

    public StatusViewModel status(AuthenticatedSession session, String applicationId) {
        ApplicationView application = applications.get(session, applicationId);
        Optional<BankCaseView> bankCase = bankCases.forApplication(applicationId)
                .filter(found -> found.companyId().equals(application.companyId()));

        String status = bankCase.map(BankCaseView::status).orElse(application.status());
        long caseVersion = bankCase.map(BankCaseView::caseVersion).orElse(0L);
        long viewVersion = application.version() + caseVersion;
        Instant updatedAt = bankCase.map(BankCaseView::updatedAt)
                .filter(at -> at.isAfter(application.updatedAt()))
                .orElse(application.updatedAt());

        List<HistoryEvent> history = new ArrayList<>();
        history.add(new HistoryEvent(applicationId + ":created", application.createdAt(), "Черновик создан"));
        applications.submittedAt(applicationId).ifPresent(at ->
                history.add(new HistoryEvent(applicationId + ":submitted", at, "Передаём заявку")));
        bankCase.ifPresent(found ->
                history.add(new HistoryEvent(found.caseId() + ":accepted", found.createdAt(), "На рассмотрении")));

        return new StatusViewModel(
                applicationId, status, viewVersion, bankCase.map(BankCaseView::caseVersion).orElse(null), updatedAt,
                false, nextAction(status, applicationId), history, applicationId + ":" + viewVersion);
    }

    static NextAction nextAction(String status, String applicationId) {
        String path = "/applications/" + applicationId;
        return switch (status) {
            case "DRAFT" -> new NextAction("CONTINUE", "Продолжить заполнение", path);
            case "NEEDS_INFO" -> new NextAction("PROVIDE_INFORMATION", "Дополнить сведения", path + "/information");
            case "APPROVED", "ALTERNATIVE" -> new NextAction("VIEW_OFFER", "Посмотреть предложение", path + "/offer");
            case "ACCEPTED", "COMPLETED", "DECLINED", "CANCELLED", "EXPIRED" ->
                    new NextAction("VIEW_RESULT", "Посмотреть результат", path);
            default -> new NextAction("WAIT", "Ожидайте решения банка", path);
        };
    }
}
