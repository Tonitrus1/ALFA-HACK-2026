package ru.alfahack.credit.integration.application;

import java.time.Instant;

public record OfferView(
        String offerId, String decisionId, String applicationId, String companyId, long version, String status,
        long amountMinor, int termMonths, String termsDisclosure, Instant validUntil) {

    /** Статус с учётом банковского времени: просроченное AVAILABLE показывается как EXPIRED. */
    public String effectiveStatus(Instant now) {
        return "AVAILABLE".equals(status) && !now.isBefore(validUntil) ? "EXPIRED" : status;
    }
}
