package ru.alfahack.credit.integration.application;

import java.time.Clock;
import java.util.Map;

import org.springframework.stereotype.Component;

import ru.alfahack.credit.integration.infrastructure.BankCaseRepository;
import ru.alfahack.credit.integration.infrastructure.InboxRepository;
import ru.alfahack.credit.integration.infrastructure.ReviewTaskRepository;
import ru.alfahack.credit.journey.application.CommandOperations;
import ru.alfahack.credit.journey.application.EventHandler;
import ru.alfahack.credit.journey.application.EventMessage;
import ru.alfahack.credit.journey.application.InformationRequests;
import ru.alfahack.credit.journey.application.Outbox;
import ru.alfahack.credit.platform.support.Ids;
import ru.alfahack.credit.platform.support.Times;

/**
 * Банк принимает ответ на RFI: NEEDS_INFO → REVIEW (CAS по caseVersion), дело рассматривается по новому
 * финансовому снимку ответа, RFI закрывается, команда RESPOND подтверждается. Повтор события — без эффекта.
 */
@Component
class InformationResponseHandler implements EventHandler {

    static final String CONSUMER = "bank-simulator-rfi";

    private final InboxRepository inbox;
    private final BankCaseRepository cases;
    private final InformationRequests requests;
    private final CommandOperations operations;
    private final ReviewTaskRepository reviews;
    private final Outbox outbox;
    private final Clock clock;

    InformationResponseHandler(InboxRepository inbox, BankCaseRepository cases, InformationRequests requests,
                               CommandOperations operations, ReviewTaskRepository reviews, Outbox outbox, Clock clock) {
        this.inbox = inbox;
        this.cases = cases;
        this.requests = requests;
        this.operations = operations;
        this.reviews = reviews;
        this.outbox = outbox;
        this.clock = clock;
    }

    @Override
    public String consumer() {
        return CONSUMER;
    }

    @Override
    public boolean handles(String eventType) {
        return "InformationResponseSubmitted".equals(eventType);
    }

    @Override
    public void handle(EventMessage event) {
        var now = Times.now(clock);
        if (!inbox.record(CONSUMER, event.eventId(), now)) {
            return;
        }
        String operationId = event.payloadString("operationId");
        BankCaseView bankCase = cases.findByApplication(event.applicationId()).orElseThrow();
        if (!"NEEDS_INFO".equals(bankCase.status())
                || !cases.transition(bankCase.caseId(), bankCase.caseVersion(), "NEEDS_INFO", "REVIEW",
                event.payloadString("amendmentId"), now)) {
            operations.complete(operationId, "FAILED", "CASE_NOT_AWAITING_INFORMATION",
                    "Банк не ожидает дополнительных сведений по заявке");
            return;
        }
        long caseVersion = bankCase.caseVersion() + 1;
        requests.close(event.payloadString("requestId"));
        operations.complete(operationId, "SUCCEEDED", "RESPONSE_ACCEPTED", "Дополнение принято банком");
        outbox.append(new EventMessage(Ids.newEventId(), "CaseStateChanged", 1, bankCase.caseId(), caseVersion,
                event.applicationId(), now, event.correlationId(), event.eventId().toString(),
                Map.of("caseId", bankCase.caseId(), "caseVersion", caseVersion, "clientStage", "REVIEW")));
        reviews.enqueue(Ids.newId(), bankCase.caseId(), caseVersion, now);
    }
}
