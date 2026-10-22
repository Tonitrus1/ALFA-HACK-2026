package ru.alfahack.credit.integration.application;

import java.time.Clock;
import java.util.Set;

import org.springframework.stereotype.Service;

import ru.alfahack.credit.access.application.AuthenticatedSession;
import ru.alfahack.credit.applications.application.ApplicationService;
import ru.alfahack.credit.integration.infrastructure.DecisionRepository;
import ru.alfahack.credit.platform.web.ApplicationException;
import ru.alfahack.credit.platform.web.ErrorKind;

/** Решение и предложения для клиента: только своя компания; MANUAL — ещё не решение. */
@Service
public class DecisionQueries {

    static final Set<String> PUBLIC_OUTCOMES = Set.of("APPROVED", "ALTERNATIVE", "NEEDS_INFO", "DECLINED");

    private final ApplicationService applications;
    private final DecisionRepository decisions;
    private final Clock clock;

    public DecisionQueries(ApplicationService applications, DecisionRepository decisions, Clock clock) {
        this.applications = applications;
        this.decisions = decisions;
        this.clock = clock;
    }

    public DecisionView decision(AuthenticatedSession session, String applicationId) {
        applications.get(session, applicationId);
        return decisions.latestForApplication(applicationId)
                .filter(found -> PUBLIC_OUTCOMES.contains(found.outcome()))
                .orElseThrow(() -> new ApplicationException(
                        ErrorKind.NOT_FOUND, "DECISION_NOT_READY", "Решение ещё не принято"));
    }

    public OfferView offer(AuthenticatedSession session, String offerId) {
        OfferView offer = decisions.offer(offerId)
                .filter(found -> found.companyId().equals(session.selectedCompanyId())
                        && session.isMemberOf(found.companyId()))
                .orElseThrow(ApplicationException::notFound);
        return new OfferView(offer.offerId(), offer.decisionId(), offer.applicationId(), offer.companyId(),
                offer.version(), offer.effectiveStatus(clock.instant()), offer.amountMinor(), offer.termMonths(),
                offer.termsDisclosure(), offer.validUntil());
    }
}
