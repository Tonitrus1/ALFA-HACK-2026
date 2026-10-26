package ru.alfahack.credit.ports.sessions;

import java.time.Instant;

/** Новая сессия; хранится только хеш токена. selectedCompanyId может быть null. */
public record NewSession(
        String sessionHash,
        String actorId,
        String selectedCompanyId,
        String csrfToken,
        Instant createdAt,
        Instant expiresAt) {
}
