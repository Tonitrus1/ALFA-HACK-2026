package ru.alfahack.credit.journey.infrastructure;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;
import java.util.Optional;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.json.JsonMapper;

import ru.alfahack.credit.journey.application.InformationRequestView;

@Repository
public class InformationRequestRepository {

    private static final TypeReference<List<InformationRequestView.Item>> ITEMS = new TypeReference<>() {
    };
    private static final String SELECT = """
            SELECT request_id, application_id, company_id, case_id, version, status, items::text AS items, deadline,
                   created_at
            FROM journey.information_request
            """;

    private final JdbcClient jdbc;
    private final JsonMapper json;

    public InformationRequestRepository(JdbcClient jdbc, JsonMapper json) {
        this.jdbc = jdbc;
        this.json = json;
    }

    public void insert(InformationRequestView request) {
        jdbc.sql("""
                        INSERT INTO journey.information_request (request_id, application_id, company_id, case_id,
                            version, status, items, deadline, created_at, updated_at)
                        VALUES (:id, :application, :company, :case, :version, :status, CAST(:items AS jsonb),
                                :deadline, :now, :now)
                        """)
                .param("id", request.requestId())
                .param("application", request.applicationId())
                .param("company", request.companyId())
                .param("case", request.caseId())
                .param("version", request.version())
                .param("status", request.status())
                .param("items", json.writeValueAsString(request.items()))
                .param("deadline", request.deadline() == null ? null : Timestamp.from(request.deadline()))
                .param("now", Timestamp.from(request.createdAt()))
                .update();
    }

    public Optional<InformationRequestView> find(String requestId) {
        return jdbc.sql(SELECT + " WHERE request_id = :id").param("id", requestId)
                .query((rs, row) -> map(rs)).optional();
    }

    public List<InformationRequestView> forApplication(String applicationId) {
        return jdbc.sql(SELECT + " WHERE application_id = :id ORDER BY created_at DESC LIMIT 100")
                .param("id", applicationId).query((rs, row) -> map(rs)).list();
    }

    public boolean transition(String requestId, String from, String to, Instant now) {
        return jdbc.sql("""
                        UPDATE journey.information_request SET status = :to, updated_at = :now
                        WHERE request_id = :id AND status = :from
                        """)
                .param("to", to).param("now", Timestamp.from(now)).param("id", requestId).param("from", from)
                .update() == 1;
    }

    private InformationRequestView map(ResultSet rs) throws SQLException {
        Timestamp deadline = rs.getTimestamp("deadline");
        return new InformationRequestView(
                rs.getString("request_id"), rs.getString("application_id"), rs.getString("company_id"),
                rs.getString("case_id"), rs.getLong("version"), rs.getString("status"),
                json.readValue(rs.getString("items"), ITEMS), deadline == null ? null : deadline.toInstant(),
                rs.getTimestamp("created_at").toInstant());
    }
}
