package ru.alfahack.credit.access.api;

import java.time.Instant;

import com.fasterxml.jackson.annotation.JsonInclude;

import ru.alfahack.credit.access.application.AuthenticatedSession;

/** Схема Session публичного контракта. */
@JsonInclude(JsonInclude.Include.NON_NULL)
record SessionResponse(
        String userId,
        String displayName,
        String companyId,
        Instant expiresAt,
        String csrfToken,
        long contextVersion) {

    static SessionResponse of(AuthenticatedSession session, String displayName) {
        return new SessionResponse(
                session.actorId(),
                displayName,
                session.selectedCompanyId(),
                session.expiresAt(),
                session.csrfToken(),
                session.contextVersion());
    }
}
