package ru.alfahack.credit.adapters.local;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.function.Supplier;

import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.simple.JdbcClient;

import ru.alfahack.credit.ports.PortErrorClass;
import ru.alfahack.credit.ports.PortException;
import ru.alfahack.credit.ports.sessions.CompanyMembership;
import ru.alfahack.credit.ports.sessions.NewSession;
import ru.alfahack.credit.ports.sessions.RevocationReceipt;
import ru.alfahack.credit.ports.sessions.Session;
import ru.alfahack.credit.ports.sessions.SessionLookup;
import ru.alfahack.credit.ports.sessions.SessionStorePort;

/**
 * Долговечные сессии в схеме access PostgreSQL: TTL, версия, отзыв и authEpoch переживают перезапуск.
 * Ошибка БД переводится в UNAVAILABLE и закрывает доступ.
 */
public class JdbcSessionAdapter implements SessionStorePort {

    private final JdbcClient jdbc;

    public JdbcSessionAdapter(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    @Override
    public SessionLookup resolve(String sessionHash, Instant now) {
        return guarded(() -> findActive(sessionHash, now)
                .<SessionLookup>map(SessionLookup.Found::new)
                .orElseGet(SessionLookup.Missing::new));
    }

    @Override
    public Session issue(NewSession newSession) {
        return guarded(() -> {
            int inserted = jdbc.sql("""
                            INSERT INTO access.session (session_hash, actor_id, selected_company_id, context_version,
                                                        csrf_token, auth_epoch, created_at, expires_at)
                            SELECT :hash, a.actor_id, :company, 1, :csrf, a.auth_epoch, :createdAt, :expiresAt
                            FROM access.actor a
                            WHERE a.actor_id = :actor AND NOT a.disabled
                            """)
                    .param("hash", newSession.sessionHash())
                    .param("company", newSession.selectedCompanyId())
                    .param("csrf", newSession.csrfToken())
                    .param("createdAt", Timestamp.from(newSession.createdAt()))
                    .param("expiresAt", Timestamp.from(newSession.expiresAt()))
                    .param("actor", newSession.actorId())
                    .update();
            if (inserted != 1) {
                throw new PortException(PortErrorClass.NOT_FOUND, "Actor is not active");
            }
            return findActive(newSession.sessionHash(), newSession.createdAt())
                    .orElseThrow(() -> new PortException(PortErrorClass.UNAVAILABLE, "Issued session is not readable"));
        });
    }

    @Override
    public Session selectCompany(
            String sessionHash, long expectedVersion, String companyId, String newCsrfToken, Instant now) {
        return guarded(() -> {
            int updated = jdbc.sql("""
                            UPDATE access.session s
                            SET selected_company_id = :company,
                                context_version = s.context_version + 1,
                                csrf_token = :csrf,
                                version = s.version + 1
                            FROM access.actor a
                            WHERE s.session_hash = :hash
                              AND s.version = :expectedVersion
                              AND s.revoked_at IS NULL
                              AND s.expires_at > :now
                              AND a.actor_id = s.actor_id
                              AND NOT a.disabled
                              AND a.auth_epoch = s.auth_epoch
                              AND EXISTS (SELECT 1 FROM access.company_membership m
                                          WHERE m.actor_id = s.actor_id AND m.company_id = :company)
                            """)
                    .param("company", companyId)
                    .param("csrf", newCsrfToken)
                    .param("hash", sessionHash)
                    .param("expectedVersion", expectedVersion)
                    .param("now", Timestamp.from(now))
                    .update();
            if (updated != 1) {
                throw new PortException(PortErrorClass.VERSION_CONFLICT, "Session changed or company is not permitted");
            }
            return findActive(sessionHash, now)
                    .orElseThrow(() -> new PortException(PortErrorClass.VERSION_CONFLICT, "Session changed"));
        });
    }

    @Override
    public RevocationReceipt revoke(String sessionHash, long expectedVersion) {
        return guarded(() -> jdbc.sql("""
                        UPDATE access.session
                        SET revoked_at = now(), version = version + 1
                        WHERE session_hash = :hash AND version = :expectedVersion AND revoked_at IS NULL
                        RETURNING session_hash, version, revoked_at
                        """)
                .param("hash", sessionHash)
                .param("expectedVersion", expectedVersion)
                .query((rs, row) -> new RevocationReceipt(
                        rs.getString("session_hash"),
                        rs.getLong("version"),
                        rs.getTimestamp("revoked_at").toInstant()))
                .optional()
                .orElseThrow(() -> new PortException(PortErrorClass.VERSION_CONFLICT, "Session changed or revoked")));
    }

    private Optional<Session> findActive(String sessionHash, Instant now) {
        Optional<Session> session = jdbc.sql("""
                        SELECT s.session_hash, s.actor_id, s.selected_company_id, s.context_version, s.csrf_token,
                               s.auth_epoch, s.expires_at, s.version
                        FROM access.session s
                        JOIN access.actor a ON a.actor_id = s.actor_id
                        WHERE s.session_hash = :hash
                          AND s.revoked_at IS NULL
                          AND s.expires_at > :now
                          AND NOT a.disabled
                          AND a.auth_epoch = s.auth_epoch
                        """)
                .param("hash", sessionHash)
                .param("now", Timestamp.from(now))
                .query((rs, row) -> new Session(
                        rs.getString("session_hash"),
                        rs.getString("actor_id"),
                        List.of(),
                        rs.getString("selected_company_id"),
                        rs.getLong("context_version"),
                        rs.getString("csrf_token"),
                        rs.getLong("auth_epoch"),
                        rs.getTimestamp("expires_at").toInstant(),
                        rs.getLong("version")))
                .optional();
        return session.map(found -> new Session(
                found.sessionHash(),
                found.actorId(),
                memberships(found.actorId()),
                found.selectedCompanyId(),
                found.contextVersion(),
                found.csrfToken(),
                found.authEpoch(),
                found.expiresAt(),
                found.version()));
    }

    private List<CompanyMembership> memberships(String actorId) {
        return jdbc.sql("""
                        SELECT company_id, role FROM access.company_membership
                        WHERE actor_id = :actor ORDER BY company_id, role
                        """)
                .param("actor", actorId)
                .query((rs, row) -> new CompanyMembership(rs.getString("company_id"), rs.getString("role")))
                .list();
    }

    private static <T> T guarded(Supplier<T> action) {
        try {
            return action.get();
        } catch (DataAccessException e) {
            throw new PortException(PortErrorClass.UNAVAILABLE, "Session store unavailable", e);
        }
    }
}
