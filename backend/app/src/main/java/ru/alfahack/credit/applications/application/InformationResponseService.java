package ru.alfahack.credit.applications.application;

import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.json.JsonMapper;

import ru.alfahack.credit.access.application.AuthenticatedSession;
import ru.alfahack.credit.access.application.CompanyAccessService;
import ru.alfahack.credit.access.application.CompanyAction;
import ru.alfahack.credit.applications.infrastructure.FinancialStatementRepository;
import ru.alfahack.credit.applications.infrastructure.InformationDraftRepository;
import ru.alfahack.credit.applications.infrastructure.RequestKeyRepository;
import ru.alfahack.credit.catalog.application.CatalogService;
import ru.alfahack.credit.journey.application.CommandOperations;
import ru.alfahack.credit.journey.application.EventMessage;
import ru.alfahack.credit.journey.application.InformationRequestView;
import ru.alfahack.credit.journey.application.InformationRequests;
import ru.alfahack.credit.journey.application.OperationView;
import ru.alfahack.credit.journey.application.Outbox;
import ru.alfahack.credit.platform.support.Digests;
import ru.alfahack.credit.platform.support.IdempotencyKeys;
import ru.alfahack.credit.platform.support.Ids;
import ru.alfahack.credit.platform.support.Times;
import ru.alfahack.credit.platform.web.ApplicationException;
import ru.alfahack.credit.platform.web.ErrorKind;

/**
 * Ответ на финансовый RFI (backend guide, раздел 3). Черновик начинается полной копией подтверждённой формы;
 * PUT меняет только запрошенные значения; ответ сравнивает draftVersion/requestVersion/requirementsVersion,
 * создаёт новый неизменяемый финансовый снимок и operation RESPOND в одном commit. Исходная анкета не меняется.
 */
@Service
public class InformationResponseService {

    public static final String RESPOND = "RESPOND";
    static final String FIELD_PREFIX = "financialStatement.values.";
    static final String SAVE_SCOPE = "RFI_FINANCIAL_SAVE";
    static final String CONFIRM_SCOPE = "RFI_FINANCIAL_CONFIRM";
    private static final TypeReference<List<ApplicationCommands.DocumentReference>> REFERENCES =
            new TypeReference<>() {
            };

    private final ApplicationService applications;
    private final InformationDraftRepository drafts;
    private final FinancialStatementRepository statements;
    private final FinancialStatementService financials;
    private final SubmissionQueries submissions;
    private final RequestKeyRepository requestKeys;
    private final InformationRequests requests;
    private final CommandOperations operations;
    private final Outbox outbox;
    private final CompanyAccessService companies;
    private final CatalogService catalog;
    private final JsonMapper json;
    private final Clock clock;

    public InformationResponseService(
            ApplicationService applications, InformationDraftRepository drafts,
            FinancialStatementRepository statements, FinancialStatementService financials,
            SubmissionQueries submissions, RequestKeyRepository requestKeys, InformationRequests requests,
            CommandOperations operations, Outbox outbox, CompanyAccessService companies, CatalogService catalog,
            JsonMapper json, Clock clock) {
        this.applications = applications;
        this.drafts = drafts;
        this.statements = statements;
        this.financials = financials;
        this.submissions = submissions;
        this.requestKeys = requestKeys;
        this.requests = requests;
        this.operations = operations;
        this.outbox = outbox;
        this.companies = companies;
        this.catalog = catalog;
        this.json = json;
        this.clock = clock;
    }

    /** Банк открыл финансовый RFI: черновик ответа — полная копия формы из снимка, на котором шло рассмотрение. */
    @Transactional(propagation = Propagation.MANDATORY)
    public void initializeDraft(InformationRequestView request, String baseFinancialSnapshotId) {
        SubmissionQueries.FinancialSnapshotData base = submissions.financialSnapshot(baseFinancialSnapshotId)
                .orElseThrow();
        ApplicationView application = applications.find(request.applicationId()).orElseThrow();
        long requirementsVersion = catalog.find(application.productId(), application.productVersion())
                .orElseThrow().requirementsVersion();
        Instant now = Times.now(clock);
        statements.upsertContainer(request.requestId(), request.applicationId(), base.statementVersion(),
                content(base.statement(), base.values()), json.writeValueAsString(base.statement()
                        .getOrDefault("sourceDocumentReferences", List.of())), true, now);
        drafts.insert(new InformationDraftView(request.requestId(), request.applicationId(), request.companyId(),
                request.version(), 1, requirementsVersion, base.statementVersion(), request.requestedFieldPaths(),
                "EDITING"), now);
    }

    public List<InformationRequestView> list(AuthenticatedSession session, String applicationId) {
        applications.get(session, applicationId);
        return requests.forApplication(applicationId);
    }

    public InformationDraftView draft(AuthenticatedSession session, String applicationId, String requestId) {
        applications.get(session, applicationId);
        return drafts.find(requestId)
                .filter(found -> found.applicationId().equals(applicationId))
                .orElseThrow(ApplicationException::notFound);
    }

    public long draftStatementVersion(InformationDraftView draft) {
        return statements.findContainer(draft.requestId(), draft.draftVersion())
                .map(FinancialStatementView::statementVersion).orElse(draft.baseStatementVersion());
    }

    /** Финансовый RFI не разрешает менять анкету, документы или пояснение — только запрошенные значения формы. */
    @Transactional
    public InformationDraftView patchDraft(AuthenticatedSession session, String applicationId, String requestId,
                                           long ifMatch, InformationCommands.DraftPatch patch) {
        InformationDraftView draft = draft(session, applicationId, requestId);
        companies.requireAction(session, draft.companyId(), CompanyAction.RESPOND);
        if (patch.hasAmendment() || patch.explanation() != null
                || (patch.documentReferences() != null && !patch.documentReferences().isEmpty())) {
            throw fieldNotRequested();
        }
        InformationDraftView locked = lockEditable(requestId, ifMatch);
        requireVersions(locked, patch.requestVersion(), patch.requirementsVersion());
        drafts.advance(requestId, ifMatch, "EDITING", Times.now(clock));
        return drafts.find(requestId).orElseThrow();
    }

    public FinancialStatementView financial(AuthenticatedSession session, String applicationId, String requestId) {
        InformationDraftView draft = draft(session, applicationId, requestId);
        return statements.findContainer(requestId, draft.draftVersion()).orElseThrow(ApplicationException::notFound);
    }

    @Transactional
    public FinancialStatementView saveFinancial(AuthenticatedSession session, String applicationId, String requestId,
                                                long ifMatch, String key, FinancialCommands.Save command) {
        InformationDraftView draft = draft(session, applicationId, requestId);
        companies.requireAction(session, draft.companyId(), CompanyAction.RESPOND);
        String digest = Digests.sha256(requestId + "|" + ifMatch + "|" + command);
        if (replayed(session, draft, SAVE_SCOPE, key, digest)) {
            return financial(session, applicationId, requestId);
        }
        InformationDraftView locked = lockEditable(requestId, ifMatch);
        requireOpen(requestId);
        FinancialStatementService.requireFullCalendarYear(command.periodStart(), command.periodEnd());
        SubmissionQueries.FinancialSnapshotData base = baseSnapshot(locked);
        FinancialStatementView.Content baseContent = content(base.statement(), base.values());
        FinancialStatementView.Content proposed = new FinancialStatementView.Content(command.periodStart(),
                command.periodEnd(), command.reportingStandard(), command.currency(), command.values(),
                command.sourceDocumentReferences());
        requireOnlyRequestedChanges(locked, baseContent, proposed);

        Instant now = Times.now(clock);
        FinancialStatementView current = statements.findContainer(requestId, locked.draftVersion()).orElseThrow();
        if (!current.content().equals(proposed)) {
            long nextVersion = statements.maxStatementVersion(applicationId) + 1;
            statements.upsertContainer(requestId, applicationId, nextVersion, proposed,
                    json.writeValueAsString(proposed.sourceDocumentReferences()), false, now);
        }
        drafts.advance(requestId, ifMatch, "EDITING", now);
        requestKeys.insert(session.actorId(), locked.companyId(), SAVE_SCOPE, key, digest, applicationId, now);
        return financial(session, applicationId, requestId);
    }

    @Transactional
    public FinancialStatementView confirmFinancial(AuthenticatedSession session, String applicationId,
                                                   String requestId, long ifMatch, String key,
                                                   FinancialCommands.Confirm command) {
        InformationDraftView draft = draft(session, applicationId, requestId);
        companies.requireAction(session, draft.companyId(), CompanyAction.RESPOND);
        String digest = Digests.sha256(requestId + "|" + ifMatch + "|" + command);
        if (replayed(session, draft, CONFIRM_SCOPE, key, digest)) {
            return financial(session, applicationId, requestId);
        }
        InformationDraftView locked = lockEditable(requestId, ifMatch);
        requireOpen(requestId);
        FinancialStatementView statement = statements.findContainer(requestId, locked.draftVersion()).orElseThrow();
        FinancialStatementService.requireConfirmable(statement, command);
        Instant now = Times.now(clock);
        if (!statement.confirmed()) {
            statements.confirmContainer(requestId, applicationId, statement.statementVersion(), session.actorId(), now);
        }
        drafts.advance(requestId, ifMatch, "EDITING", now);
        requestKeys.insert(session.actorId(), locked.companyId(), CONFIRM_SCOPE, key, digest, applicationId, now);
        return financial(session, applicationId, requestId);
    }

    /**
     * Ответ банку (202): повтор по ключу возвращает исходный receipt; затем версии черновика, запроса и
     * требований, подтверждённая версия формы; один commit — снимок, черновик SUBMITTED, RFI RESPONDED,
     * operation RESPOND и outbox InformationResponseSubmitted.
     */
    @Transactional
    public ApplicationCommands.Receipt respond(AuthenticatedSession session, String applicationId, String requestId,
                                               String key, InformationCommands.Response response) {
        IdempotencyKeys.validate(key);
        InformationDraftView draft = draft(session, applicationId, requestId);
        String companyId = draft.companyId();
        String digest = Digests.sha256(requestId + "|" + response);
        Optional<OperationView> stored = operations.findByKey(session.actorId(), companyId, RESPOND, key);
        if (stored.isPresent()) {
            return receipt(stored.get(), digest);
        }
        companies.requireAction(session, companyId, CompanyAction.RESPOND);
        Instant now = Times.now(clock);
        String operationId = Ids.newId();
        if (operations.start(new OperationView(operationId, session.actorId(), companyId, RESPOND, key, digest,
                applicationId, requestId, "PENDING", null, null, now, now)) == CommandOperations.Start.DUPLICATE) {
            return receipt(operations.findByKey(session.actorId(), companyId, RESPOND, key).orElseThrow(), digest);
        }

        InformationDraftView locked = drafts.lock(requestId).orElseThrow(ApplicationException::notFound);
        if (!"EDITING".equals(locked.state()) || locked.draftVersion() != response.draftVersion()) {
            throw draftConflict();
        }
        requireVersions(locked, response.requestVersion(), response.requirementsVersion());
        if (response.hasAmendment() || response.explanation() != null || !response.documentIds().isEmpty()
                || !response.documentReferences().isEmpty()) {
            throw draftConflict();
        }
        FinancialStatementView statement = statements.findContainer(requestId, locked.draftVersion()).orElseThrow();
        if (!statement.confirmed() || statement.statementVersion() != response.financialStatementVersion()) {
            throw new ApplicationException(ErrorKind.UNPROCESSABLE, "FINANCIAL_CONFIRMATION_REQUIRED",
                    "Нужно подтвердить финансовые показатели ответа");
        }
        companies.recheckAction(session.actorId(), companyId, CompanyAction.RESPOND);
        String snapshotId = financials.snapshotForContainer(requestId, applicationId, companyId,
                statement.statementVersion()).orElseThrow();
        if (!drafts.advance(requestId, locked.draftVersion(), "SUBMITTED", now) || !requests.markResponded(requestId)) {
            throw draftConflict();
        }
        outbox.append(new EventMessage(Ids.newEventId(), "InformationResponseSubmitted", 1, requestId,
                locked.requestVersion(), applicationId, now, operationId, operationId,
                Map.of("requestId", requestId,
                        "requestVersion", locked.requestVersion(),
                        "amendmentId", snapshotId,
                        "amendmentVersion", statement.statementVersion(),
                        "operationId", operationId,
                        "externalRequestId", "respond:" + requestId + ":" + locked.requestVersion())));
        return new ApplicationCommands.Receipt(operationId, applicationId, now);
    }

    private void requireOnlyRequestedChanges(InformationDraftView draft, FinancialStatementView.Content base,
                                             FinancialStatementView.Content proposed) {
        boolean sameFrame = base.periodStart().equals(proposed.periodStart())
                && base.periodEnd().equals(proposed.periodEnd())
                && base.reportingStandard().equals(proposed.reportingStandard())
                && base.currency().equals(proposed.currency())
                && base.sourceDocumentReferences().equals(proposed.sourceDocumentReferences());
        if (!sameFrame) {
            throw fieldNotRequested();
        }
        for (FinancialField field : FinancialField.values()) {
            boolean requested = draft.requestedFields().contains(FIELD_PREFIX + field.wireName());
            Long before = base.values().get(field);
            Long after = proposed.values().get(field);
            if (!requested && !Objects.equals(before, after)) {
                throw fieldNotRequested();
            }
        }
    }

    private SubmissionQueries.FinancialSnapshotData baseSnapshot(InformationDraftView draft) {
        String snapshotId = statements.snapshotId(draft.applicationId(), draft.baseStatementVersion()).orElseThrow();
        return submissions.financialSnapshot(snapshotId).orElseThrow();
    }

    private InformationDraftView lockEditable(String requestId, long ifMatch) {
        InformationDraftView locked = drafts.lock(requestId).orElseThrow(ApplicationException::notFound);
        if (!"EDITING".equals(locked.state())) {
            throw new ApplicationException(ErrorKind.CONFLICT, "INFORMATION_DRAFT_SUBMITTED", "Ответ уже отправлен");
        }
        if (locked.draftVersion() != ifMatch) {
            throw draftConflict();
        }
        return locked;
    }

    private void requireOpen(String requestId) {
        if (!requests.find(requestId).map(found -> "OPEN".equals(found.status())).orElse(false)) {
            throw new ApplicationException(ErrorKind.CONFLICT, "INFORMATION_REQUEST_CHANGED", "Запрос уже закрыт");
        }
    }

    private void requireVersions(InformationDraftView draft, long requestVersion, long requirementsVersion) {
        if (draft.requestVersion() != requestVersion) {
            throw new ApplicationException(ErrorKind.CONFLICT, "INFORMATION_REQUEST_CHANGED", "Запрос банка изменился");
        }
        if (draft.requirementsVersion() != requirementsVersion) {
            throw new ApplicationException(ErrorKind.CONFLICT, "DOCUMENT_REQUIREMENTS_CHANGED",
                    "Требования к документам изменились");
        }
    }

    private boolean replayed(AuthenticatedSession session, InformationDraftView draft, String scope, String key,
                             String digest) {
        if (key == null || key.isBlank() || key.length() > 128) {
            throw new ApplicationException(
                    ErrorKind.INVALID_REQUEST, "INVALID_IDEMPOTENCY_KEY", "Некорректный Idempotency-Key");
        }
        return requestKeys.findDigest(session.actorId(), draft.companyId(), scope, key)
                .map(stored -> {
                    if (!stored.equals(digest)) {
                        throw IdempotencyKeys.reused();
                    }
                    return true;
                })
                .orElse(false);
    }

    @SuppressWarnings("unchecked")
    private FinancialStatementView.Content content(Map<String, Object> statement, FinancialValues values) {
        Object refs = statement.getOrDefault("sourceDocumentReferences", List.of());
        List<ApplicationCommands.DocumentReference> references =
                json.readValue(json.writeValueAsString(refs), REFERENCES);
        return new FinancialStatementView.Content(
                LocalDate.parse((String) statement.get("periodStart")),
                LocalDate.parse((String) statement.get("periodEnd")),
                (String) statement.get("reportingStandard"), (String) statement.get("currency"), values, references);
    }

    private static ApplicationCommands.Receipt receipt(OperationView operation, String digest) {
        if (!operation.bodyDigest().equals(digest)) {
            throw IdempotencyKeys.reused();
        }
        return new ApplicationCommands.Receipt(operation.operationId(), operation.applicationId(),
                operation.createdAt());
    }

    private static ApplicationException fieldNotRequested() {
        return new ApplicationException(ErrorKind.UNPROCESSABLE, "FIELD_NOT_REQUESTED",
                "Можно изменить только запрошенные банком сведения");
    }

    private static ApplicationException draftConflict() {
        return new ApplicationException(ErrorKind.CONFLICT, "INFORMATION_DRAFT_CONFLICT",
                "Черновик ответа изменился; обновите данные");
    }
}
