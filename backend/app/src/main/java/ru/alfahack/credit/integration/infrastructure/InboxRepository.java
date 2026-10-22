package ru.alfahack.credit.integration.infrastructure;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.UUID;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

@Repository
public class InboxRepository {

    private final JdbcClient jdbc;

    public InboxRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    /** true — событие обрабатывается впервые этим consumer. */
    public boolean record(String consumer, UUID eventId, Instant now) {
        return jdbc.sql("""
                        INSERT INTO integration.inbox (consumer, event_id, processed_at) VALUES (:consumer, :id, :now)
                        ON CONFLICT DO NOTHING
                        """)
                .param("consumer", consumer)
                .param("id", eventId)
                .param("now", Timestamp.from(now))
                .update() == 1;
    }
}
