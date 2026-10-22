package ru.alfahack.credit.integration.application;

import java.time.Clock;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Map;

import org.springframework.stereotype.Component;

import ru.alfahack.credit.journey.application.CommandOperations;
import ru.alfahack.credit.journey.application.EventHandler;
import ru.alfahack.credit.journey.application.EventMessage;
import ru.alfahack.credit.journey.application.Outbox;
import ru.alfahack.credit.integration.infrastructure.BankCaseRepository;
import ru.alfahack.credit.integration.infrastructure.InboxRepository;
import ru.alfahack.credit.platform.support.Ids;

/**
 * Банковский симулятор — отдельный авторитет решения внутри процесса. На SubmissionRequested создаёт дело
 * (дедуп по externalRequestId), подтверждает команду SUBMIT и публикует CaseAccepted (SUBMITTED → REVIEW).
 * Inbox (consumer, eventId) фиксируется атомарно с эффектом; повтор события ничего не меняет.
 */
@Component
class BankSimulator implements EventHandler {

    static final String CONSUMER = "bank-simulator";

    private final InboxRepository inbox;
    private final BankCaseRepository cases;
    private final CommandOperations operations;
    private final Outbox outbox;
    private final Clock clock;

    BankSimulator(
            InboxRepository inbox, BankCaseRepository cases, CommandOperations operations, Outbox outbox, Clock clock) {
        this.inbox = inbox;
        this.cases = cases;
        this.operations = operations;
        this.outbox = outbox;
        this.clock = clock;
    }

    @Override
    public String consumer() {
        return CONSUMER;
    }

    @Override
    public boolean handles(String eventType) {
        return "SubmissionRequested".equals(eventType);
    }

    @Override
    public void handle(EventMessage event) {
        Instant now = clock.instant().truncatedTo(ChronoUnit.MICROS);
        if (!inbox.record(CONSUMER, event.eventId(), now)) {
            return;
        }
        String externalRequestId = event.payloadString("externalRequestId");
        String operationId = event.payloadString("operationId");
        String companyId = operations.findCompany(operationId).orElseThrow();

        BankCaseView bankCase = new BankCaseView(
                "case-" + Ids.newId(), event.applicationId(), companyId, externalRequestId, 1, "REVIEW", now, now);
        if (!cases.insertIfAbsent(bankCase)) {
            return;
        }
        operations.complete(operationId, "SUCCEEDED", "CASE_ACCEPTED", "Заявка принята банком на рассмотрение");
        outbox.append(new EventMessage(
                Ids.newEventId(), "CaseAccepted", 1, bankCase.caseId(), bankCase.caseVersion(),
                event.applicationId(), now, event.correlationId(), event.eventId().toString(),
                Map.of(
                        "caseId", bankCase.caseId(),
                        "caseVersion", bankCase.caseVersion(),
                        "externalRequestId", externalRequestId,
                        "clientStage", "REVIEW")));
    }
}
