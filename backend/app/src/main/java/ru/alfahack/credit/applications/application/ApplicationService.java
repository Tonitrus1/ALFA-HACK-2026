package ru.alfahack.credit.applications.application;

import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.Instant;
import java.util.Base64;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import tools.jackson.databind.json.JsonMapper;

import ru.alfahack.credit.access.application.AuthenticatedSession;
import ru.alfahack.credit.access.application.CompanyAccessService;
import ru.alfahack.credit.access.application.CompanyAction;
import ru.alfahack.credit.applications.domain.ApplicationStatus;
import ru.alfahack.credit.applications.infrastructure.ApplicationRepository;
import ru.alfahack.credit.applications.infrastructure.SubmissionSnapshotRepository;
import ru.alfahack.credit.catalog.application.CatalogService;
import ru.alfahack.credit.catalog.application.ProductView;
import ru.alfahack.credit.journey.application.CommandOperations;
import ru.alfahack.credit.journey.application.EventMessage;
import ru.alfahack.credit.journey.application.OperationView;
import ru.alfahack.credit.journey.application.Outbox;
import ru.alfahack.credit.platform.support.Digests;
import ru.alfahack.credit.platform.support.IdempotencyKeys;
import ru.alfahack.credit.platform.support.Ids;
import ru.alfahack.credit.platform.support.Times;
import ru.alfahack.credit.platform.web.ApplicationException;
import ru.alfahack.credit.platform.web.ErrorKind;

/**
 * Черновики и отправка заявки. Create — синхронный 201 с повтором по ключу; submit — долговечная команда:
 * один commit сохраняет заявку, неизменяемый пакет, operation и outbox (backend guide, раздел 2).
 */
@Service
public class ApplicationService {

    public static final String SUBMIT = "SUBMIT";

    private static final Set<String> CLEARABLE = Set.of(
            "business.annualRevenue", "business.annualExpenses", "business.currentDebt",
            "business.businessAgeMonths", "business.activityDescription", "business.sourceConfirmationVersion");

    public record Created(ApplicationView application, boolean replayed) {
    }

    public record Page(List<ApplicationView> items, String nextCursor) {
    }

    private final ApplicationRepository applications;
    private final SubmissionSnapshotRepository snapshots;
    private final CompanyAccessService companies;
    private final CatalogService catalog;
    private final CommandOperations operations;
    private final Outbox outbox;
    private final SubmissionPrerequisites prerequisites;
    private final JsonMapper json;
    private final Clock clock;

    public ApplicationService(
            ApplicationRepository applications,
            SubmissionSnapshotRepository snapshots,
            CompanyAccessService companies,
            CatalogService catalog,
            CommandOperations operations,
            Outbox outbox,
            SubmissionPrerequisites prerequisites,
            JsonMapper json,
            Clock clock) {
        this.applications = applications;
        this.snapshots = snapshots;
        this.companies = companies;
        this.catalog = catalog;
        this.operations = operations;
        this.outbox = outbox;
        this.prerequisites = prerequisites;
        this.json = json;
        this.clock = clock;
    }

    @Transactional
    public Created create(AuthenticatedSession session, String idempotencyKey, ApplicationCommands.Create command) {
        IdempotencyKeys.validate(idempotencyKey);
        companies.requireAction(session, command.companyId(), CompanyAction.CREATE_APPLICATION);
        String digest = Digests.sha256(command.toString());

        Optional<ApplicationView> existing =
                applications.findByCreateKey(session.actorId(), command.companyId(), idempotencyKey);
        if (existing.isPresent()) {
            return replay(existing.get(), digest);
        }

        ProductView product = catalog.find(command.productId(), command.productVersion())
                .filter(ProductView::active)
                .orElseThrow(() -> new ApplicationException(
                        ErrorKind.UNPROCESSABLE, "PRODUCT_NOT_AVAILABLE", "Продукт или его версия недоступны"));

        Instant now = Times.now(clock);
        ApplicationView draft = new ApplicationView(
                Ids.newId(), command.companyId(), product.productId(), product.version(),
                ApplicationStatus.DRAFT.name(), 1, command.purpose(), command.amountMinor(), command.termMonths(),
                BusinessData.EMPTY, null, null, session.actorId(), idempotencyKey, digest, now, now);
        if (!applications.insertIfAbsent(draft)) {
            return replay(applications.findByCreateKey(session.actorId(), command.companyId(), idempotencyKey)
                    .orElseThrow(), digest);
        }
        return new Created(applications.find(draft.applicationId()).orElseThrow(), false);
    }

    public Page list(AuthenticatedSession session, String companyId, String cursor, int limit) {
        companies.requireSelectedCompany(session, companyId);
        Cursor after = Cursor.parse(cursor);
        List<ApplicationView> rows = applications.list(companyId, after.updatedAt(), after.applicationId(), limit + 1);
        if (rows.size() <= limit) {
            return new Page(rows, null);
        }
        List<ApplicationView> page = List.copyOf(rows.subList(0, limit));
        return new Page(page, Cursor.of(page.getLast()));
    }

    /** Заявка выбранной компании; чужая неотличима от несуществующей. */
    public ApplicationView get(AuthenticatedSession session, String applicationId) {
        return applications.find(applicationId)
                .filter(application -> isSelectedCompany(session, application))
                .orElseThrow(ApplicationException::notFound);
    }

    /** Время первой отправки (создания неизменяемого пакета), если заявка отправлена. */
    public Optional<Instant> submittedAt(String applicationId) {
        return snapshots.submittedAt(applicationId);
    }

    @Transactional
    public ApplicationView patch(
            AuthenticatedSession session, String applicationId, long expectedVersion, ApplicationCommands.Patch patch) {
        ApplicationView current = get(session, applicationId);
        companies.requireAction(session, current.companyId(), CompanyAction.EDIT_DRAFT);
        if (!ApplicationStatus.DRAFT.name().equals(current.status())) {
            throw new ApplicationException(
                    ErrorKind.CONFLICT, "APPLICATION_NOT_EDITABLE", "Заявка уже отправлена и не редактируется");
        }
        if (current.version() != expectedVersion) {
            throw draftVersionConflict();
        }
        ApplicationView updated = apply(current, patch);
        if (!applications.updateDraft(updated, expectedVersion, Times.now(clock))) {
            throw draftVersionConflict();
        }
        return applications.find(applicationId).orElseThrow();
    }

    /**
     * Порядок команды: аутентификация и компания → сохранённый ключ (повтор возвращает прежний receipt до
     * проверок состояния) → роль, версии и предусловия → один commit. Полномочия перепроверяются перед commit.
     */
    @Transactional
    public ApplicationCommands.Receipt submit(
            AuthenticatedSession session, String applicationId, String idempotencyKey, ApplicationCommands.Submit command) {
        IdempotencyKeys.validate(idempotencyKey);
        ApplicationView current = get(session, applicationId);
        String companyId = current.companyId();
        String digest = Digests.sha256(applicationId + "|" + command);

        Optional<OperationView> stored = operations.findByKey(session.actorId(), companyId, SUBMIT, idempotencyKey);
        if (stored.isPresent()) {
            return receipt(stored.get(), digest);
        }
        companies.requireAction(session, companyId, CompanyAction.SUBMIT);

        Instant now = Times.now(clock);
        String operationId = Ids.newId();
        OperationView operation = new OperationView(
                operationId, session.actorId(), companyId, SUBMIT, idempotencyKey, digest, applicationId,
                applicationId, "PENDING", null, null, now, now);
        if (operations.start(operation) == CommandOperations.Start.DUPLICATE) {
            return receipt(operations.findByKey(session.actorId(), companyId, SUBMIT, idempotencyKey).orElseThrow(),
                    digest);
        }

        ApplicationView application = applications.lock(applicationId).orElseThrow(ApplicationException::notFound);
        if (!ApplicationStatus.DRAFT.name().equals(application.status())) {
            throw new ApplicationException(
                    ErrorKind.CONFLICT, "APPLICATION_ALREADY_SUBMITTED", "Заявка уже отправлена");
        }
        if (application.version() != command.expectedVersion()) {
            throw draftVersionConflict();
        }
        ProductView product = catalog.find(application.productId(), application.productVersion()).orElseThrow();
        if (product.requirementsVersion() != command.requirementsVersion()) {
            throw new ApplicationException(
                    ErrorKind.CONFLICT, "DOCUMENT_REQUIREMENTS_CHANGED", "Требования к пакету изменились");
        }
        requireMatchingDocumentReferences(command);
        if (!prerequisites.documentsClean(application, command.documentReferences())) {
            throw documentReferencesMismatch();
        }
        if (!prerequisites.consentsValid(application, product, command.consentRecordIds())) {
            throw new ApplicationException(
                    ErrorKind.UNPROCESSABLE, "CONSENT_REQUIRED", "Нет действующих согласий для отправки");
        }
        if (!product.allowsAmount(application.amountMinor()) || !product.allowsTerm(application.termMonths())) {
            throw new ApplicationException(
                    ErrorKind.UNPROCESSABLE, "TERMS_OUT_OF_RANGE", "Сумма или срок вне условий продукта");
        }
        String financialSnapshotId = prerequisites
                .confirmedFinancialSnapshot(application, command.financialStatementVersion())
                .orElse(null);
        if (product.financialRequired() && financialSnapshotId == null) {
            throw new ApplicationException(ErrorKind.UNPROCESSABLE, "FINANCIAL_CONFIRMATION_REQUIRED",
                    "Нужно подтвердить восемь финансовых показателей");
        }
        companies.recheckAction(session.actorId(), companyId, CompanyAction.SUBMIT);

        if (!applications.markSubmitted(
                applicationId, command.expectedVersion(), command.financialStatementVersion(), financialSnapshotId, now)) {
            throw draftVersionConflict();
        }
        long snapshotVersion = command.expectedVersion() + 1;
        String snapshotId = Ids.newId();
        String packageJson = json.writeValueAsString(submissionPackage(
                application, product, command, financialSnapshotId, snapshotVersion));
        snapshots.insert(snapshotId, applicationId, snapshotVersion, packageJson, Digests.sha256(packageJson), now);

        outbox.append(new EventMessage(
                Ids.newEventId(), "SubmissionRequested", 1, applicationId, snapshotVersion, applicationId, now,
                operationId, operationId,
                Map.of(
                        "submissionId", snapshotId,
                        "snapshotVersion", snapshotVersion,
                        "snapshotRef", snapshotId,
                        "operationId", operationId,
                        "externalRequestId", "submit:" + applicationId + ":" + snapshotVersion)));
        return new ApplicationCommands.Receipt(operationId, applicationId, now);
    }

    private Created replay(ApplicationView existing, String digest) {
        if (!existing.createBodyDigest().equals(digest)) {
            throw IdempotencyKeys.reused();
        }
        return new Created(existing, true);
    }

    private static ApplicationCommands.Receipt receipt(OperationView operation, String digest) {
        if (!operation.bodyDigest().equals(digest)) {
            throw IdempotencyKeys.reused();
        }
        return new ApplicationCommands.Receipt(
                operation.operationId(), operation.applicationId(), operation.createdAt());
    }

    private static boolean isSelectedCompany(AuthenticatedSession session, ApplicationView application) {
        return application.companyId().equals(session.selectedCompanyId()) && session.isMemberOf(application.companyId());
    }

    private static ApplicationView apply(ApplicationView current, ApplicationCommands.Patch patch) {
        Set<String> clear = patch.clearFields() == null ? Set.of() : patch.clearFields();
        if (!CLEARABLE.containsAll(clear)) {
            throw new ApplicationException(ErrorKind.UNPROCESSABLE, "PATCH_FIELD_NOT_CLEARABLE", "Поле нельзя очистить");
        }
        BusinessData set = patch.business() == null ? BusinessData.EMPTY : patch.business();
        BusinessData base = current.business();
        BusinessData merged = new BusinessData(
                field("business.annualRevenue", set.annualRevenueMinor(), base.annualRevenueMinor(), clear),
                field("business.annualExpenses", set.annualExpensesMinor(), base.annualExpensesMinor(), clear),
                field("business.currentDebt", set.currentDebtMinor(), base.currentDebtMinor(), clear),
                field("business.businessAgeMonths", set.businessAgeMonths(), base.businessAgeMonths(), clear),
                field("business.activityDescription", set.activityDescription(), base.activityDescription(), clear),
                field("business.sourceConfirmationVersion", set.sourceConfirmationVersion(),
                        base.sourceConfirmationVersion(), clear));
        return new ApplicationView(
                current.applicationId(), current.companyId(), current.productId(), current.productVersion(),
                current.status(), current.version(),
                patch.purpose() != null ? patch.purpose() : current.purpose(),
                patch.amountMinor() != null ? patch.amountMinor() : current.amountMinor(),
                patch.termMonths() != null ? patch.termMonths() : current.termMonths(),
                merged, current.financialStatementVersion(), current.financialSnapshotId(), current.createdBy(),
                current.createKey(), current.createBodyDigest(), current.createdAt(), current.updatedAt());
    }

    private static <T> T field(String path, T value, T current, Set<String> clear) {
        if (clear.contains(path)) {
            if (value != null) {
                throw new ApplicationException(ErrorKind.UNPROCESSABLE, "PATCH_FIELD_CONFLICT",
                        "Поле одновременно записывается и очищается");
            }
            return null;
        }
        return value != null ? value : current;
    }

    private static void requireMatchingDocumentReferences(ApplicationCommands.Submit command) {
        Set<String> ids = new HashSet<>(command.documentIds());
        Set<String> referenced = new HashSet<>();
        for (ApplicationCommands.DocumentReference reference : command.documentReferences()) {
            if (!referenced.add(reference.documentId())) {
                throw documentReferencesMismatch();
            }
        }
        if (ids.size() != command.documentIds().size() || !ids.equals(referenced)) {
            throw documentReferencesMismatch();
        }
    }

    private static Map<String, Object> submissionPackage(
            ApplicationView application, ProductView product, ApplicationCommands.Submit command,
            String financialSnapshotId, long snapshotVersion) {
        Map<String, Object> pkg = new LinkedHashMap<>();
        pkg.put("applicationId", application.applicationId());
        pkg.put("companyId", application.companyId());
        pkg.put("snapshotVersion", snapshotVersion);
        pkg.put("productId", product.productId());
        pkg.put("productVersion", product.version());
        pkg.put("requirementsVersion", product.requirementsVersion());
        pkg.put("purpose", application.purpose());
        pkg.put("amountMinor", application.amountMinor());
        pkg.put("currency", "RUB");
        pkg.put("termMonths", application.termMonths());
        pkg.put("business", application.business());
        pkg.put("financialStatementVersion", command.financialStatementVersion());
        pkg.put("financialSnapshotId", financialSnapshotId);
        pkg.put("documentReferences", command.documentReferences());
        pkg.put("consentRecordIds", command.consentRecordIds());
        return pkg;
    }

    private static ApplicationException draftVersionConflict() {
        return new ApplicationException(
                ErrorKind.CONFLICT, "DRAFT_VERSION_CONFLICT", "Черновик изменён; обновите данные");
    }

    private static ApplicationException documentReferencesMismatch() {
        return new ApplicationException(
                ErrorKind.UNPROCESSABLE, "DOCUMENT_REFERENCES_MISMATCH", "Ссылки на документы не совпадают");
    }

    /** Непрозрачный курсор списка: base64url("epochMicros:applicationId"). */
    record Cursor(Instant updatedAt, String applicationId) {

        static Cursor parse(String cursor) {
            if (cursor == null) {
                return new Cursor(null, null);
            }
            try {
                String raw = new String(Base64.getUrlDecoder().decode(cursor), StandardCharsets.UTF_8);
                int separator = raw.indexOf(':');
                long micros = Long.parseLong(raw.substring(0, separator));
                Instant updatedAt = Instant.ofEpochSecond(micros / 1_000_000, (micros % 1_000_000) * 1_000);
                return new Cursor(updatedAt, raw.substring(separator + 1));
            } catch (RuntimeException e) {
                throw new ApplicationException(ErrorKind.INVALID_REQUEST, "INVALID_CURSOR", "Некорректный курсор");
            }
        }

        static String of(ApplicationView last) {
            Instant at = last.updatedAt();
            long micros = at.getEpochSecond() * 1_000_000 + at.getNano() / 1_000;
            return Base64.getUrlEncoder().withoutPadding()
                    .encodeToString((micros + ":" + last.applicationId()).getBytes(StandardCharsets.UTF_8));
        }
    }
}
