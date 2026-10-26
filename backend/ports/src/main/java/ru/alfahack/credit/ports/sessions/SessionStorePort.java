package ru.alfahack.credit.ports.sessions;

import java.time.Instant;

/**
 * Хранилище сессий (Redis / SessionStorePort). Локальный провайдер — JdbcSessionAdapter.
 * Неизвестная, истёкшая, отозванная сессия или сессия с устаревшим authEpoch — {@link SessionLookup.Missing}.
 * Отказ хранилища не открывает доступ (no fail-open): адаптер бросает PortException(UNAVAILABLE).
 *
 * <p>Каталог задаёт resolve/revoke; issue и selectCompany добавлены для входа и смены компании
 * (rotate contextVersion по data-model) и требуют подтверждения в контракте P01.
 */
public interface SessionStorePort {

    SessionLookup resolve(String sessionHash, Instant now);

    Session issue(NewSession newSession);

    /**
     * CAS-смена выбранной компании: version должна совпасть, членство в компании проверяется
     * в той же операции. contextVersion и version увеличиваются, csrfToken ротируется.
     * Несовпадение версии или отсутствие членства — PortException(VERSION_CONFLICT).
     */
    Session selectCompany(String sessionHash, long expectedVersion, String companyId, String newCsrfToken, Instant now);

    RevocationReceipt revoke(String sessionHash, long expectedVersion);
}
