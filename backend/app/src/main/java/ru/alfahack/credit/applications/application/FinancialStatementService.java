package ru.alfahack.credit.applications.application;

import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.MonthDay;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import tools.jackson.databind.json.JsonMapper;

import ru.alfahack.credit.access.application.AuthenticatedSession;
import ru.alfahack.credit.access.application.CompanyAccessService;
import ru.alfahack.credit.access.application.CompanyAction;
import ru.alfahack.credit.applications.domain.ApplicationStatus;
import ru.alfahack.credit.applications.infrastructure.ApplicationRepository;
import ru.alfahack.credit.applications.infrastructure.FinancialStatementRepository;
import ru.alfahack.credit.applications.infrastructure.RequestKeyRepository;
import ru.alfahack.credit.platform.support.Digests;
import ru.alfahack.credit.platform.support.Ids;
import ru.alfahack.credit.platform.support.Times;
import ru.alfahack.credit.platform.web.ApplicationException;
import ru.alfahack.credit.platform.web.ErrorKind;

/**
 * Финансовая форма DEMO Financial v1 черновика заявки (backend guide, раздел 3).
 * Неполный черновик разрешён; любое изменение содержимого создаёт новую statementVersion и сбрасывает
 * подтверждение. Подтверждение требует все 8 значений, равенства и точные ссылки на источники;
 * provenance формирует сервер. Снимок для пакета создаётся только в транзакции submit.
 */
@Service
public class FinancialStatementService {

    static final String SAVE_SCOPE = "FINANCIAL_SAVE";
    static final String CONFIRM_SCOPE = "FINANCIAL_CONFIRM";

    private final ApplicationRepository applications;
    private final FinancialStatementRepository statements;
    private final RequestKeyRepository requestKeys;
    private final CompanyAccessService companies;
    private final DocumentReferenceGate documents;
    private final JsonMapper json;
    private final Clock clock;

    public FinancialStatementService(
            ApplicationRepository applications,
            FinancialStatementRepository statements,
            RequestKeyRepository requestKeys,
            CompanyAccessService companies,
            DocumentReferenceGate documents,
            JsonMapper json,
            Clock clock) {
        this.applications = applications;
        this.statements = statements;
        this.requestKeys = requestKeys;
        this.companies = companies;
        this.documents = documents;
        this.json = json;
        this.clock = clock;
    }

    public FinancialStatementView get(AuthenticatedSession session, String applicationId) {
        ApplicationView application = load(session, applicationId);
        return statements.find(applicationId, application.version())
                .orElseThrow(() -> new ApplicationException(
                        ErrorKind.NOT_FOUND, "FINANCIAL_STATEMENT_NOT_STARTED", "Финансовая анкета ещё не заполнена"));
    }

    @Transactional
    public FinancialStatementView save(
            AuthenticatedSession session, String applicationId, long ifMatchVersion, String idempotencyKey,
            FinancialCommands.Save command) {
        ApplicationView application = load(session, applicationId);
        companies.requireAction(session, application.companyId(), CompanyAction.EDIT_DRAFT);
        String digest = Digests.sha256(applicationId + "|" + ifMatchVersion + "|" + command);
        if (replayed(session, application, SAVE_SCOPE, idempotencyKey, digest)) {
            return get(session, applicationId);
        }
        ApplicationView locked = lockEditable(applicationId, ifMatchVersion);
        requireFullCalendarYear(command.periodStart(), command.periodEnd());
        if (!documents.allClean(locked, command.sourceDocumentReferences())) {
            throw documentReferencesMismatch();
        }

        Instant now = Times.now(clock);
        FinancialStatementView.Content content = new FinancialStatementView.Content(
                command.periodStart(), command.periodEnd(), command.reportingStandard(), command.currency(),
                command.values(), command.sourceDocumentReferences());
        Optional<FinancialStatementView> current = statements.find(applicationId, locked.version());
        if (current.isEmpty() || !current.get().content().equals(content)) {
            long nextVersion = current.map(found -> found.statementVersion() + 1).orElse(1L);
            statements.upsert(applicationId, nextVersion, content, json.writeValueAsString(
                    content.sourceDocumentReferences()), now);
            bumpApplication(locked, now);
        }
        requestKeys.insert(session.actorId(), locked.companyId(), SAVE_SCOPE, idempotencyKey, digest, applicationId, now);
        return get(session, applicationId);
    }

    @Transactional
    public FinancialStatementView confirm(
            AuthenticatedSession session, String applicationId, long ifMatchVersion, String idempotencyKey,
            FinancialCommands.Confirm command) {
        ApplicationView application = load(session, applicationId);
        companies.requireAction(session, application.companyId(), CompanyAction.EDIT_DRAFT);
        String digest = Digests.sha256(applicationId + "|" + ifMatchVersion + "|" + command);
        if (replayed(session, application, CONFIRM_SCOPE, idempotencyKey, digest)) {
            return get(session, applicationId);
        }
        ApplicationView locked = lockEditable(applicationId, ifMatchVersion);
        FinancialStatementView statement = statements.find(applicationId, locked.version())
                .orElseThrow(() -> incomplete(FinancialField.wireNames()));
        requireConfirmable(statement, command);

        Instant now = Times.now(clock);
        if (!statement.confirmed()) {
            statements.confirm(applicationId, statement.statementVersion(), session.actorId(), now);
            bumpApplication(locked, now);
        }
        requestKeys.insert(
                session.actorId(), locked.companyId(), CONFIRM_SCOPE, idempotencyKey, digest, applicationId, now);
        return get(session, applicationId);
    }

    /** Проверки подтверждения: версия, все 8 полей, равенства, точные ссылки на источники. */
    static void requireConfirmable(FinancialStatementView statement, FinancialCommands.Confirm command) {
        if (statement.statementVersion() != command.expectedStatementVersion()) {
            throw new ApplicationException(ErrorKind.CONFLICT, "FINANCIAL_STATEMENT_VERSION_CONFLICT",
                    "Финансовая анкета изменилась; проверьте значения");
        }
        if (!new HashSet<>(command.confirmedFieldNames()).equals(new HashSet<>(FinancialField.wireNames()))
                || command.confirmedFieldNames().size() != FinancialField.values().length) {
            throw new ApplicationException(ErrorKind.INVALID_REQUEST, "INVALID_REQUEST",
                    "Нужно подтвердить все восемь показателей");
        }
        List<FinancialField> missing = statement.values().missing();
        if (!missing.isEmpty()) {
            throw incomplete(missing.stream().map(FinancialField::wireName).toList());
        }
        List<String> violations = statement.values().invariantViolations();
        if (!violations.isEmpty()) {
            throw new ApplicationException(ErrorKind.UNPROCESSABLE, "FINANCIAL_INVARIANT_VIOLATED",
                    "Показатели не согласованы: " + String.join(", ", violations));
        }
        if (!new HashSet<>(command.documentReferences()).equals(new HashSet<>(statement.sourceDocumentReferences()))
                || command.documentReferences().size() != statement.sourceDocumentReferences().size()) {
            throw documentReferencesMismatch();
        }
    }

    /**
     * Для submit: подтверждённая форма именно этой версии → неизменяемый FinancialSnapshot в текущей транзакции.
     * Повтор для той же версии возвращает тот же снимок.
     */
    @Transactional(propagation = Propagation.MANDATORY)
    public Optional<String> snapshotForSubmit(ApplicationView application, long statementVersion) {
        return snapshotForContainer(application.applicationId(), application.applicationId(), application.companyId(),
                statementVersion);
    }

    /** Неизменяемый снимок подтверждённой формы контейнера (исходной анкеты или ответа на RFI). */
    @Transactional(propagation = Propagation.MANDATORY)
    public Optional<String> snapshotForContainer(
            String containerId, String applicationId, String companyId, long statementVersion) {
        Optional<FinancialStatementView> statement = statements.findContainer(containerId, 1)
                .filter(found -> found.confirmed() && found.statementVersion() == statementVersion);
        if (statement.isEmpty()) {
            return Optional.empty();
        }
        FinancialStatementView confirmed = statement.get();
        String statementJson = json.writeValueAsString(snapshotStatement(confirmed));
        String provenanceJson = json.writeValueAsString(confirmed.provenance());
        statements.insertSnapshotIfAbsent(
                Ids.newId(), applicationId, companyId, statementVersion,
                Digests.sha256(statementJson), statementJson, provenanceJson, Times.now(clock));
        return statements.snapshotId(applicationId, statementVersion);
    }

    private ApplicationView load(AuthenticatedSession session, String applicationId) {
        return applications.find(applicationId)
                .filter(found -> found.companyId().equals(session.selectedCompanyId())
                        && session.isMemberOf(found.companyId()))
                .orElseThrow(ApplicationException::notFound);
    }

    private boolean replayed(
            AuthenticatedSession session, ApplicationView application, String scope, String key, String digest) {
        if (key == null || key.isBlank() || key.length() > 128) {
            throw new ApplicationException(
                    ErrorKind.INVALID_REQUEST, "INVALID_IDEMPOTENCY_KEY", "Некорректный Idempotency-Key");
        }
        return requestKeys.findDigest(session.actorId(), application.companyId(), scope, key)
                .map(stored -> {
                    if (!stored.equals(digest)) {
                        throw new ApplicationException(ErrorKind.CONFLICT, "IDEMPOTENCY_KEY_REUSED",
                                "Ключ уже использован для другого запроса");
                    }
                    return true;
                })
                .orElse(false);
    }

    private ApplicationView lockEditable(String applicationId, long ifMatchVersion) {
        ApplicationView locked = applications.lock(applicationId).orElseThrow(ApplicationException::notFound);
        if (!ApplicationStatus.DRAFT.name().equals(locked.status())) {
            throw new ApplicationException(
                    ErrorKind.CONFLICT, "APPLICATION_NOT_EDITABLE", "Заявка уже отправлена и не редактируется");
        }
        if (locked.version() != ifMatchVersion) {
            throw new ApplicationException(
                    ErrorKind.CONFLICT, "DRAFT_VERSION_CONFLICT", "Черновик изменён; обновите данные");
        }
        return locked;
    }

    private void bumpApplication(ApplicationView locked, Instant now) {
        if (!applications.bumpVersion(locked.applicationId(), locked.version(), now)) {
            throw new ApplicationException(
                    ErrorKind.CONFLICT, "DRAFT_VERSION_CONFLICT", "Черновик изменён; обновите данные");
        }
    }

    static void requireFullCalendarYear(LocalDate start, LocalDate end) {
        boolean fullYear = start != null && end != null
                && start.getYear() == end.getYear()
                && MonthDay.from(start).equals(MonthDay.of(1, 1))
                && MonthDay.from(end).equals(MonthDay.of(12, 31));
        if (!fullYear) {
            throw new ApplicationException(ErrorKind.UNPROCESSABLE, "FINANCIAL_PERIOD_INVALID",
                    "Период должен быть одним полным календарным годом");
        }
    }

    private static Map<String, Object> snapshotStatement(FinancialStatementView statement) {
        Map<String, Object> values = new LinkedHashMap<>();
        for (FinancialField field : FinancialField.values()) {
            values.put(field.wireName(), statement.values().get(field));
        }
        Map<String, Object> snapshot = new LinkedHashMap<>();
        snapshot.put("statementVersion", statement.statementVersion());
        snapshot.put("periodStart", statement.periodStart().toString());
        snapshot.put("periodEnd", statement.periodEnd().toString());
        snapshot.put("reportingStandard", statement.reportingStandard());
        snapshot.put("currency", statement.currency());
        snapshot.put("values", values);
        snapshot.put("sourceDocumentReferences", statement.sourceDocumentReferences());
        return snapshot;
    }

    static ApplicationException incomplete(List<String> missing) {
        return new ApplicationException(ErrorKind.UNPROCESSABLE, "FINANCIAL_VALUES_INCOMPLETE",
                "Не заполнены показатели: " + String.join(", ", missing));
    }

    static ApplicationException documentReferencesMismatch() {
        return new ApplicationException(
                ErrorKind.UNPROCESSABLE, "DOCUMENT_REFERENCES_MISMATCH", "Ссылки на документы не совпадают");
    }
}
