package ru.alfahack.credit.ports.sessions;

import java.time.Instant;
import java.util.List;

/**
 * Серверная сессия. companyMemberships читаются из авторитетного источника при каждом resolve,
 * а не из закешированной роли браузера.
 */
public record Session(
        String sessionHash,
        String actorId,
        List<CompanyMembership> companyMemberships,
        String selectedCompanyId,
        long contextVersion,
        String csrfToken,
        long authEpoch,
        Instant expiresAt,
        long version) {

    public Session {
        companyMemberships = List.copyOf(companyMemberships);
    }
}
