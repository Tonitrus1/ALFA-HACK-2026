package ru.alfahack.credit.integration.application;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionTemplate;

import ru.alfahack.credit.applications.application.ApplicationView;
import ru.alfahack.credit.applications.application.FinancialField;
import ru.alfahack.credit.applications.application.InformationResponseService;
import ru.alfahack.credit.applications.application.SubmissionQueries;
import ru.alfahack.credit.catalog.application.CatalogService;
import ru.alfahack.credit.catalog.application.ProductView;
import ru.alfahack.credit.integration.domain.DemoPolicyV1;
import ru.alfahack.credit.integration.infrastructure.BankCaseRepository;
import ru.alfahack.credit.integration.infrastructure.DecisionRepository;
import ru.alfahack.credit.integration.infrastructure.ReviewTaskRepository;
import ru.alfahack.credit.journey.application.EventMessage;
import ru.alfahack.credit.journey.application.InformationRequestView;
import ru.alfahack.credit.journey.application.InformationRequests;
import ru.alfahack.credit.journey.application.Outbox;
import ru.alfahack.credit.ml.application.RiskAssessment;
import ru.alfahack.credit.ml.application.RiskGateway;
import ru.alfahack.credit.platform.support.Ids;
import ru.alfahack.credit.platform.support.Times;

/**
 * Рассмотрение дела симулятором: задача с арендой → данные пакета и точного финансового снимка → риск
 * вне транзакции (только если политике нужен прогноз) → в одной транзакции CAS дела по caseVersion, решение,
 * предложение, RFI и события. Устаревшая версия дела закрывает задачу без эффекта.
 */
@Component
public class ReviewWorker {

    static final Duration LEASE = Duration.ofMinutes(2);
    static final Duration OFFER_VALIDITY = Duration.ofHours(24);
    static final String DISCLOSURE = "Предварительные условия синтетического demo-продукта. Не является офертой "
            + "банка; ставка и итоговые условия определяются при оформлении.";

    private final ReviewTaskRepository tasks;
    private final BankCaseRepository cases;
    private final DecisionRepository decisions;
    private final SubmissionQueries submissions;
    private final CatalogService catalog;
    private final RiskGateway risk;
    private final InformationRequests requests;
    private final InformationResponseService responses;
    private final Outbox outbox;
    private final TransactionTemplate transactions;
    private final Clock clock;

    public ReviewWorker(ReviewTaskRepository tasks, BankCaseRepository cases, DecisionRepository decisions,
                        SubmissionQueries submissions, CatalogService catalog, RiskGateway risk,
                        InformationRequests requests, InformationResponseService responses, Outbox outbox,
                        TransactionTemplate transactions, Clock clock) {
        this.tasks = tasks;
        this.cases = cases;
        this.decisions = decisions;
        this.submissions = submissions;
        this.catalog = catalog;
        this.risk = risk;
        this.requests = requests;
        this.responses = responses;
        this.outbox = outbox;
        this.transactions = transactions;
        this.clock = clock;
    }

    /** Одна задача; false — очередь пуста. */
    public boolean processOnce() {
        Instant claimedAt = Times.now(clock);
        Optional<ReviewTaskRepository.Task> claimed =
                transactions.execute(status -> tasks.claim(claimedAt, claimedAt.plus(LEASE)));
        if (claimed.isEmpty()) {
            return false;
        }
        ReviewTaskRepository.Task task = claimed.get();
        BankCaseView bankCase = cases.find(task.caseId()).orElseThrow();
        if (!"REVIEW".equals(bankCase.status()) || bankCase.caseVersion() != task.caseVersion()) {
            transactions.executeWithoutResult(status -> tasks.done(task.taskId(), Times.now(clock)));
            return true;
        }
        SubmissionQueries.SubmittedApplication submitted =
                submissions.submitted(bankCase.applicationId()).orElseThrow();
        ApplicationView application = submitted.application();
        SubmissionQueries.FinancialSnapshotData financial =
                submissions.financialSnapshot(bankCase.financialSnapshotId()).orElseThrow();
        ProductView product = catalog.find(application.productId(), application.productVersion()).orElseThrow();
        boolean alreadyRequested = requests.forApplication(application.applicationId()).stream()
                .anyMatch(request -> !"OPEN".equals(request.status()));

        DemoPolicyV1.Input input = new DemoPolicyV1.Input(product.minAmountMinor(), product.maxAmountMinor(),
                product.minBusinessAgeMonths(), application.amountMinor(), application.termMonths(),
                application.business().businessAgeMonths(), application.business().annualRevenueMinor(),
                values(financial), alreadyRequested);
        Optional<DemoPolicyV1.Decision> early = DemoPolicyV1.beforeRisk(input);
        if (early.isPresent()) {
            record(task, bankCase, application, financial, early.get(), Optional.empty(), "NOT_REQUIRED");
            return true;
        }
        Optional<RiskAssessment> assessment = risk.assess(new RiskGateway.RiskInput(application.applicationId(),
                submitted.submissionSnapshotId(), financial.financialSnapshotId(), financial.digest(),
                financial.statementVersion(), mlStatement(financial.statement())));
        DemoPolicyV1.Decision decision = DemoPolicyV1.withRisk(input, assessment.map(RiskAssessment::score));
        record(task, bankCase, application, financial, decision, assessment,
                assessment.map(RiskAssessment::mode).orElse("UNAVAILABLE"));
        return true;
    }

    private void record(ReviewTaskRepository.Task task, BankCaseView bankCase, ApplicationView application,
                        SubmissionQueries.FinancialSnapshotData financial, DemoPolicyV1.Decision decision,
                        Optional<RiskAssessment> assessment, String riskMode) {
        transactions.executeWithoutResult(status -> {
            Instant now = Times.now(clock);
            String outcome = decision.outcome().name();
            if (!cases.transition(bankCase.caseId(), bankCase.caseVersion(), "REVIEW", outcome, null, now)) {
                tasks.done(task.taskId(), now);
                return;
            }
            long caseVersion = bankCase.caseVersion() + 1;
            String decisionId = Ids.newId();
            List<String> offerIds = decision.offerAmountMinor() == null ? List.of() : List.of(Ids.newId());
            decisions.insertDecision(new DecisionView(decisionId, bankCase.caseId(), application.applicationId(),
                    caseVersion, outcome, decision.publicExplanation(), DemoPolicyV1.VERSION, decision.reasonCodes(),
                    assessment.map(RiskAssessment::inferenceId).orElse(null), riskMode,
                    financial.financialSnapshotId(), offerIds, now));
            for (String offerId : offerIds) {
                decisions.insertOffer(new OfferView(offerId, decisionId, application.applicationId(),
                        application.companyId(), 1, "AVAILABLE", decision.offerAmountMinor(),
                        decision.offerTermMonths(), DISCLOSURE, now.plus(OFFER_VALIDITY)), now);
            }
            String causation = task.taskId();
            if (decision.outcome() == DemoPolicyV1.Outcome.NEEDS_INFO) {
                openInformationRequest(bankCase, application, financial, decision, caseVersion, now, causation);
            } else if (decision.outcome() == DemoPolicyV1.Outcome.MANUAL) {
                outbox.append(new EventMessage(Ids.newEventId(), "CaseStateChanged", 1, bankCase.caseId(),
                        caseVersion, application.applicationId(), now, causation, causation,
                        Map.of("caseId", bankCase.caseId(), "caseVersion", caseVersion, "clientStage", "MANUAL")));
            } else {
                outbox.append(new EventMessage(Ids.newEventId(), "DecisionRecorded", 1, bankCase.caseId(),
                        caseVersion, application.applicationId(), now, causation, causation,
                        Map.of("caseId", bankCase.caseId(), "caseVersion", caseVersion, "decisionId", decisionId,
                                "outcome", outcome, "offerIds", offerIds)));
            }
            tasks.done(task.taskId(), now);
        });
    }

    private void openInformationRequest(BankCaseView bankCase, ApplicationView application,
                                        SubmissionQueries.FinancialSnapshotData financial,
                                        DemoPolicyV1.Decision decision, long caseVersion, Instant now,
                                        String causation) {
        String requestId = Ids.newId();
        List<InformationRequestView.Item> items = decision.requestedFieldPaths().stream()
                .map(path -> new InformationRequestView.Item(Ids.newId(), "FIELD", label(path),
                        decision.publicExplanation(), true, path, null))
                .toList();
        InformationRequestView request = new InformationRequestView(requestId, application.applicationId(),
                application.companyId(), bankCase.caseId(), 1, "OPEN", items, now.plus(Duration.ofDays(5)), now);
        requests.open(request);
        responses.initializeDraft(request, financial.financialSnapshotId());
        outbox.append(new EventMessage(Ids.newEventId(), "InformationRequested", 1, bankCase.caseId(), caseVersion,
                application.applicationId(), now, causation, causation,
                Map.of("caseId", bankCase.caseId(), "caseVersion", caseVersion, "requestId", requestId,
                        "requestVersion", 1L, "requestedItemIds",
                        items.stream().map(InformationRequestView.Item::itemId).toList())));
    }

    private static Map<String, Long> values(SubmissionQueries.FinancialSnapshotData financial) {
        Map<String, Long> values = new HashMap<>();
        for (FinancialField field : FinancialField.values()) {
            values.put(field.wireName(), financial.values().get(field));
        }
        return values;
    }

    /** MLFinancialInput: точная форма снимка без служебного statementVersion. */
    private static Map<String, Object> mlStatement(Map<String, Object> statement) {
        Map<String, Object> copy = new HashMap<>(statement);
        copy.remove("statementVersion");
        return copy;
    }

    private static String label(String path) {
        return switch (path) {
            case "financialStatement.values.revenueMinor" -> "Выручка за год";
            case "financialStatement.values.netProfitMinor" -> "Чистая прибыль";
            default -> "Финансовый показатель";
        };
    }
}
