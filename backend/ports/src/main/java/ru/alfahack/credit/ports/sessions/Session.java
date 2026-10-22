package ru.alfahack.credit.ports.sessions;

import java.time.Instant;
import java.util.List;

/** Членство проверяется по авторитетному источнику, а не по закешированной роли браузера. */
public record Session(
        String actorId,
        List<CompanyMembership> companyMemberships,
        long authEpoch,
        Instant expiresAt,
        long version) {

    public Session {
        companyMemberships = List.copyOf(companyMemberships);
    }
}
