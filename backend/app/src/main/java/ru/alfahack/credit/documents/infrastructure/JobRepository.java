package ru.alfahack.credit.documents.infrastructure;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.Optional;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

/**
 * Задания SCAN/EXTRACT с арендой: каждый захват увеличивает generation и выдаёт новый токен (хранится хеш).
 * Результат принимается только от текущего поколения с непросроченной арендой.
 */
@Repository
public class JobRepository {

    public record Lease(
            String jobId, String documentId, String jobType, String objectVersion, long generation,
            Instant leaseUntil, int attempts) {
    }

    private final JdbcClient jdbc;

    public JobRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    public void insert(String jobId, String documentId, String jobType, String objectVersion, Instant now) {
        jdbc.sql("""
                        INSERT INTO documents.document_job (job_id, document_id, job_type, object_version, state,
                                                            next_attempt_at, created_at, updated_at)
                        VALUES (:id, :document, :type, :objectVersion, 'PENDING', :now, :now, :now)
                        ON CONFLICT (document_id, job_type, object_version) DO NOTHING
                        """)
                .param("id", jobId).param("document", documentId).param("type", jobType)
                .param("objectVersion", objectVersion).param("now", Timestamp.from(now))
                .update();
    }

    /** Захват готового или брошенного (истёкшая аренда) задания; занятые строки пропускаются. */
    public Optional<Lease> claim(String jobType, String workerId, String tokenHash, Instant now, Instant leaseUntil) {
        return jdbc.sql("""
                        UPDATE documents.document_job j
                        SET state = 'LEASED', generation = j.generation + 1, worker_id = :worker,
                            lease_token_hash = :token, lease_until = :leaseUntil, updated_at = :now
                        WHERE j.job_id = (
                            SELECT job_id FROM documents.document_job
                            WHERE job_type = :type AND next_attempt_at <= :now
                              AND (state = 'PENDING' OR (state = 'LEASED' AND lease_until < :now))
                            ORDER BY next_attempt_at, created_at
                            LIMIT 1
                            FOR UPDATE SKIP LOCKED)
                        RETURNING j.job_id, j.document_id, j.job_type, j.object_version, j.generation, j.lease_until,
                                  j.attempts
                        """)
                .param("worker", workerId).param("token", tokenHash).param("leaseUntil", Timestamp.from(leaseUntil))
                .param("now", Timestamp.from(now)).param("type", jobType)
                .query((rs, row) -> new Lease(
                        rs.getString("job_id"), rs.getString("document_id"), rs.getString("job_type"),
                        rs.getString("object_version"), rs.getLong("generation"),
                        rs.getTimestamp("lease_until").toInstant(), rs.getInt("attempts")))
                .optional();
    }

    /** Текущая аренда, если поколение, worker, токен и срок совпадают; блокирует строку задания. */
    public Optional<Lease> lockCurrentLease(
            String jobId, String jobType, long generation, String workerId, String tokenHash, Instant now) {
        return jdbc.sql("""
                        SELECT job_id, document_id, job_type, object_version, generation, lease_until, attempts
                        FROM documents.document_job
                        WHERE job_id = :id AND job_type = :type AND state = 'LEASED' AND generation = :generation
                          AND worker_id = :worker AND lease_token_hash = :token AND lease_until > :now
                        FOR UPDATE
                        """)
                .param("id", jobId).param("type", jobType).param("generation", generation).param("worker", workerId)
                .param("token", tokenHash).param("now", Timestamp.from(now))
                .query((rs, row) -> new Lease(
                        rs.getString("job_id"), rs.getString("document_id"), rs.getString("job_type"),
                        rs.getString("object_version"), rs.getLong("generation"),
                        rs.getTimestamp("lease_until").toInstant(), rs.getInt("attempts")))
                .optional();
    }

    public void renew(String jobId, Instant leaseUntil, Instant now) {
        jdbc.sql("UPDATE documents.document_job SET lease_until = :until, updated_at = :now WHERE job_id = :id")
                .param("until", Timestamp.from(leaseUntil)).param("now", Timestamp.from(now)).param("id", jobId)
                .update();
    }

    public void finish(String jobId, String state, String error, Instant now) {
        jdbc.sql("""
                        UPDATE documents.document_job
                        SET state = :state, last_error = :error, lease_token_hash = NULL, lease_until = NULL,
                            updated_at = :now
                        WHERE job_id = :id
                        """)
                .param("state", state).param("error", error).param("now", Timestamp.from(now)).param("id", jobId)
                .update();
    }

    /** Ошибка проверки: задание возвращается в очередь с backoff, после лимита — видимый FAILED. */
    public void retryOrFail(String jobId, int attempts, boolean failed, Instant nextAttemptAt, String error, Instant now) {
        jdbc.sql("""
                        UPDATE documents.document_job
                        SET state = CASE WHEN :failed THEN 'FAILED' ELSE 'PENDING' END, attempts = :attempts,
                            next_attempt_at = :next, last_error = :error, lease_token_hash = NULL, lease_until = NULL,
                            updated_at = :now
                        WHERE job_id = :id
                        """)
                .param("failed", failed).param("attempts", attempts).param("next", Timestamp.from(nextAttemptAt))
                .param("error", error).param("now", Timestamp.from(now)).param("id", jobId)
                .update();
    }
}
