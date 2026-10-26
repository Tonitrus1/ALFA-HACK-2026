package ru.alfahack.credit.journey.infrastructure;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.Optional;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

import ru.alfahack.credit.journey.application.OperationView;

@Repository
public class OperationRepository {

    private static final String SELECT = """
            SELECT operation_id, actor_id, company_id, command_type, client_key, body_digest, application_id,
                   resource_id, state, result_code, safe_message, created_at, updated_at
            FROM journey.command_operation
            """;

    private final JdbcClient jdbc;

    public OperationRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    public Optional<OperationView> findByKey(String actorId, String companyId, String commandType, String clientKey) {
        return jdbc.sql(SELECT + """
                        WHERE actor_id = :actor AND company_id = :company AND command_type = :type AND client_key = :key
                        """)
                .param("actor", actorId)
                .param("company", companyId)
                .param("type", commandType)
                .param("key", clientKey)
                .query((rs, row) -> map(rs))
                .optional();
    }

    public Optional<OperationView> findById(String operationId) {
        return jdbc.sql(SELECT + " WHERE operation_id = :id")
                .param("id", operationId)
                .query((rs, row) -> map(rs))
                .optional();
    }

    /** INSERT ... ON CONFLICT DO NOTHING по уникальному ключу идемпотентности; ждёт конкурирующую транзакцию. */
    public boolean insertIfAbsent(OperationView operation) {
        return jdbc.sql("""
                        INSERT INTO journey.command_operation (operation_id, actor_id, company_id, command_type, client_key,
                                                               body_digest, application_id, resource_id, state,
                                                               result_code, safe_message, created_at, updated_at)
                        VALUES (:id, :actor, :company, :type, :key, :digest, :application, :resource, :state,
                                :resultCode, :safeMessage, :createdAt, :updatedAt)
                        ON CONFLICT (actor_id, company_id, command_type, client_key) DO NOTHING
                        """)
                .param("id", operation.operationId())
                .param("actor", operation.actorId())
                .param("company", operation.companyId())
                .param("type", operation.commandType())
                .param("key", operation.clientKey())
                .param("digest", operation.bodyDigest())
                .param("application", operation.applicationId())
                .param("resource", operation.resourceId())
                .param("state", operation.state())
                .param("resultCode", operation.resultCode())
                .param("safeMessage", operation.safeMessage())
                .param("createdAt", Timestamp.from(operation.createdAt()))
                .param("updatedAt", Timestamp.from(operation.updatedAt()))
                .update() == 1;
    }

    public void complete(String operationId, String state, String resultCode, String safeMessage, Instant now) {
        jdbc.sql("""
                        UPDATE journey.command_operation
                        SET state = :state, result_code = :resultCode, safe_message = :safeMessage, updated_at = :now
                        WHERE operation_id = :id AND state IN ('PENDING', 'RECONCILING')
                        """)
                .param("state", state)
                .param("resultCode", resultCode)
                .param("safeMessage", safeMessage)
                .param("now", Timestamp.from(now))
                .param("id", operationId)
                .update();
    }

    private static OperationView map(ResultSet rs) throws SQLException {
        return new OperationView(
                rs.getString("operation_id"),
                rs.getString("actor_id"),
                rs.getString("company_id"),
                rs.getString("command_type"),
                rs.getString("client_key"),
                rs.getString("body_digest"),
                rs.getString("application_id"),
                rs.getString("resource_id"),
                rs.getString("state"),
                rs.getString("result_code"),
                rs.getString("safe_message"),
                rs.getTimestamp("created_at").toInstant(),
                rs.getTimestamp("updated_at").toInstant());
    }
}
