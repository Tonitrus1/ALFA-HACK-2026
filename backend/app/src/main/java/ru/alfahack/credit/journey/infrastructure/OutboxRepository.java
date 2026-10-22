package ru.alfahack.credit.journey.infrastructure;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;
import java.util.UUID;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

import tools.jackson.databind.json.JsonMapper;

import ru.alfahack.credit.journey.application.EventMessage;

@Repository
public class OutboxRepository {

    public record ClaimedEvent(EventMessage event, int attempts) {
    }

    private final JdbcClient jdbc;
    private final JsonMapper json;

    public OutboxRepository(JdbcClient jdbc, JsonMapper json) {
        this.jdbc = jdbc;
        this.json = json;
    }

    public void insert(EventMessage event, Instant now) {
        jdbc.sql("""
                        INSERT INTO journey.outbox (event_id, event_type, aggregate_id, aggregate_version, application_id,
                                                    envelope, next_attempt_at, created_at)
                        VALUES (:id, :type, :aggregate, :version, :application, CAST(:envelope AS jsonb), :now, :now)
                        """)
                .param("id", event.eventId())
                .param("type", event.eventType())
                .param("aggregate", event.aggregateId())
                .param("version", event.aggregateVersion())
                .param("application", event.applicationId())
                .param("envelope", json.writeValueAsString(event))
                .param("now", Timestamp.from(now))
                .update();
    }

    /** Захват готовых событий с lease; занятые другим worker строки пропускаются (SKIP LOCKED). */
    public List<ClaimedEvent> claim(String worker, Instant now, Instant leaseUntil, int batch) {
        return jdbc.sql("""
                        UPDATE journey.outbox o
                        SET lease_owner = :worker, lease_expires_at = :leaseUntil
                        WHERE o.event_id IN (
                            SELECT event_id FROM journey.outbox
                            WHERE state = 'PENDING' AND next_attempt_at <= :now
                              AND (lease_expires_at IS NULL OR lease_expires_at < :now)
                            ORDER BY created_at
                            LIMIT :batch
                            FOR UPDATE SKIP LOCKED)
                        RETURNING o.envelope::text AS envelope, o.attempts, o.created_at
                        """)
                .param("worker", worker)
                .param("leaseUntil", Timestamp.from(leaseUntil))
                .param("now", Timestamp.from(now))
                .param("batch", batch)
                .query((rs, row) -> new ClaimedEvent(
                        json.readValue(rs.getString("envelope"), EventMessage.class), rs.getInt("attempts")))
                .list();
    }

    public boolean markDelivered(UUID eventId, String worker, Instant now) {
        return jdbc.sql("""
                        UPDATE journey.outbox
                        SET state = 'DELIVERED', delivered_at = :now, lease_owner = NULL, lease_expires_at = NULL
                        WHERE event_id = :id AND lease_owner = :worker AND state = 'PENDING'
                        """)
                .param("now", Timestamp.from(now))
                .param("id", eventId)
                .param("worker", worker)
                .update() == 1;
    }

    public void markFailedAttempt(
            UUID eventId, String worker, int attempts, boolean poison, Instant nextAttemptAt, String error) {
        jdbc.sql("""
                        UPDATE journey.outbox
                        SET attempts = :attempts,
                            state = CASE WHEN :poison THEN 'FAILED' ELSE 'PENDING' END,
                            next_attempt_at = :next,
                            last_error = :error,
                            lease_owner = NULL,
                            lease_expires_at = NULL
                        WHERE event_id = :id AND lease_owner = :worker
                        """)
                .param("attempts", attempts)
                .param("poison", poison)
                .param("next", Timestamp.from(nextAttemptAt))
                .param("error", error)
                .param("id", eventId)
                .param("worker", worker)
                .update();
    }
}
