package ru.alfahack.credit.integration.infrastructure;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.Optional;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

/** Очередь рассмотрения: одна задача на (дело, версия); захват с арендой через SKIP LOCKED. */
@Repository
public class ReviewTaskRepository {

    public record Task(String taskId, String caseId, long caseVersion) {
    }

    private final JdbcClient jdbc;

    public ReviewTaskRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    public void enqueue(String taskId, String caseId, long caseVersion, Instant now) {
        jdbc.sql("""
                        INSERT INTO integration.review_task (task_id, case_id, case_version, state, created_at, updated_at)
                        VALUES (:id, :case, :version, 'PENDING', :now, :now)
                        ON CONFLICT (case_id, case_version) DO NOTHING
                        """)
                .param("id", taskId).param("case", caseId).param("version", caseVersion)
                .param("now", Timestamp.from(now))
                .update();
    }

    public Optional<Task> claim(Instant now, Instant leaseUntil) {
        return jdbc.sql("""
                        UPDATE integration.review_task t SET state = 'LEASED', lease_until = :until, updated_at = :now
                        WHERE t.task_id = (
                            SELECT task_id FROM integration.review_task
                            WHERE state = 'PENDING' OR (state = 'LEASED' AND lease_until < :now)
                            ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED)
                        RETURNING t.task_id, t.case_id, t.case_version
                        """)
                .param("until", Timestamp.from(leaseUntil)).param("now", Timestamp.from(now))
                .query((rs, row) -> new Task(rs.getString("task_id"), rs.getString("case_id"),
                        rs.getLong("case_version")))
                .optional();
    }

    public void done(String taskId, Instant now) {
        jdbc.sql("UPDATE integration.review_task SET state = 'DONE', lease_until = NULL, updated_at = :now "
                        + "WHERE task_id = :id")
                .param("now", Timestamp.from(now)).param("id", taskId).update();
    }
}
