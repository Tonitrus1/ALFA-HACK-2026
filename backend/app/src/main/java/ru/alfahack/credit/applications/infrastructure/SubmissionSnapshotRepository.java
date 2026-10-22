package ru.alfahack.credit.applications.infrastructure;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.Optional;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

/** Неизменяемые пакеты отправки; UPDATE/DELETE запрещены триггером. */
@Repository
public class SubmissionSnapshotRepository {

    private final JdbcClient jdbc;

    public SubmissionSnapshotRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    public void insert(String snapshotId, String applicationId, long version, String packageJson, String digest,
                       Instant createdAt) {
        jdbc.sql("""
                        INSERT INTO applications.submission_snapshot
                            (snapshot_id, application_id, version, package, package_digest, created_at)
                        VALUES (:id, :application, :version, CAST(:package AS jsonb), :digest, :createdAt)
                        """)
                .param("id", snapshotId)
                .param("application", applicationId)
                .param("version", version)
                .param("package", packageJson)
                .param("digest", digest)
                .param("createdAt", Timestamp.from(createdAt))
                .update();
    }

    public record SnapshotRef(String snapshotId, long version) {
    }

    public Optional<SnapshotRef> latest(String applicationId) {
        return jdbc.sql("""
                        SELECT snapshot_id, version FROM applications.submission_snapshot
                        WHERE application_id = :application ORDER BY version DESC LIMIT 1
                        """)
                .param("application", applicationId)
                .query((rs, row) -> new SnapshotRef(rs.getString("snapshot_id"), rs.getLong("version")))
                .optional();
    }

    public Optional<Instant> submittedAt(String applicationId) {
        return jdbc.sql("""
                        SELECT min(created_at) AS submitted_at FROM applications.submission_snapshot
                        WHERE application_id = :application
                        """)
                .param("application", applicationId)
                .query((rs, row) -> Optional.ofNullable(rs.getTimestamp("submitted_at")).map(Timestamp::toInstant))
                .single();
    }
}
