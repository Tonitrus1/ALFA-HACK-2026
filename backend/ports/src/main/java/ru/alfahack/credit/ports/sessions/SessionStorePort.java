package ru.alfahack.credit.ports.sessions;

import java.time.Instant;

/**
 * Хранилище сессий (Redis / SessionStorePort). Локальный провайдер — JdbcSessionAdapter.
 * Неизвестная сессия запрещает доступ; отказ хранилища не открывает доступ (no fail-open).
 */
public interface SessionStorePort {

    SessionLookup resolve(String sessionHash, Instant now);

    RevocationReceipt revoke(String sessionHash, long expectedVersion);
}
