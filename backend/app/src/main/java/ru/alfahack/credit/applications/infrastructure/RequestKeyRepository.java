package ru.alfahack.credit.applications.infrastructure;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.Optional;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

/** Ключи идемпотентности синхронных изменений формы; уникальность обеспечивает PRIMARY KEY. */
@Repository
public class RequestKeyRepository {

    private final JdbcClient jdbc;

    public RequestKeyRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    public Optional<String> findDigest(String actorId, String companyId, String scope, String key) {
        return jdbc.sql("""
                        SELECT body_digest FROM applications.request_key
                        WHERE actor_id = :actor AND company_id = :company AND scope = :scope AND client_key = :key
                        """)
                .param("actor", actorId)
                .param("company", companyId)
                .param("scope", scope)
                .param("key", key)
                .query(String.class)
                .optional();
    }

    public void insert(String actorId, String companyId, String scope, String key, String digest, String applicationId,
                       Instant now) {
        jdbc.sql("""
                        INSERT INTO applications.request_key
                            (actor_id, company_id, scope, client_key, body_digest, application_id, created_at)
                        VALUES (:actor, :company, :scope, :key, :digest, :application, :now)
                        """)
                .param("actor", actorId)
                .param("company", companyId)
                .param("scope", scope)
                .param("key", key)
                .param("digest", digest)
                .param("application", applicationId)
                .param("now", Timestamp.from(now))
                .update();
    }
}
