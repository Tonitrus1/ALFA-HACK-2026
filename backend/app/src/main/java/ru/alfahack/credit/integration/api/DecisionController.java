package ru.alfahack.credit.integration.api;

import java.time.Instant;
import java.util.List;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RestController;

import ru.alfahack.credit.access.application.AuthenticatedSession;
import ru.alfahack.credit.integration.application.DecisionQueries;
import ru.alfahack.credit.integration.application.DecisionView;
import ru.alfahack.credit.integration.application.OfferView;
import ru.alfahack.credit.platform.support.Money;

@RestController
class DecisionController {

    /** Схема Decision: внутренние коды причин и score клиенту не раскрываются. */
    record Decision(String decisionId, long caseVersion, String outcome, String publicExplanation,
                    List<String> offerIds) {
    }

    record Offer(String offerId, String applicationId, long version, String status, Money amount, long termMonths,
                 String termsDisclosure, Instant validUntil) {
    }

    private final DecisionQueries decisions;

    DecisionController(DecisionQueries decisions) {
        this.decisions = decisions;
    }

    @GetMapping("/api/v1/applications/{applicationId}/decision")
    Decision decision(AuthenticatedSession session, @RequestHeader("X-Company-Context") long context,
                      @PathVariable String applicationId) {
        DecisionView view = decisions.decision(session, applicationId);
        return new Decision(view.decisionId(), view.caseVersion(), view.outcome(), view.publicExplanation(),
                view.offerIds());
    }

    @GetMapping("/api/v1/offers/{offerId}")
    Offer offer(AuthenticatedSession session, @RequestHeader("X-Company-Context") long context,
                @PathVariable String offerId) {
        OfferView view = decisions.offer(session, offerId);
        return new Offer(view.offerId(), view.applicationId(), view.version(), view.status(),
                Money.rub(view.amountMinor()), view.termMonths(), view.termsDisclosure(), view.validUntil());
    }
}
