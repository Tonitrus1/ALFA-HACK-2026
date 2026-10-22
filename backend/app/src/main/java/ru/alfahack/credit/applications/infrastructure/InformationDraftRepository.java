package ru.alfahack.credit.applications.infrastructure;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.Arrays;
import java.util.List;
import java.util.Optional;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

import ru.alfahack.credit.applications.application.InformationDraftView;

@Repository
public class InformationDraftRepository {

    private final JdbcClient jdbc;

    public InformationDraftRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    public void insert(InformationDraftView draft, Instant now) {
        jdbc.sql("""
                        INSERT INTO applications.information_draft (request_id, application_id, company_id,
                            request_version, draft_version, requirements_version, base_statement_version,
                            requested_fields, state, created_at, updated_at)
                        VALUES (:id, :application, :company, :requestVersion, 1, :requirementsVersion, :baseVersion,
                                :fields, 'EDITING', :now, :now)
                        """)
                .param("id", draft.requestId())
                .param("application", draft.applicationId())
                .param("company", draft.companyId())
                .param("requestVersion", draft.requestVersion())
                .param("requirementsVersion", draft.requirementsVersion())
                .param("baseVersion", draft.baseStatementVersion())
                .param("fields", draft.requestedFields().toArray(String[]::new))
                .param("now", Timestamp.from(now))
                .update();
    }

    public Optional<InformationDraftView> find(String requestId) {
        return query(" WHERE request_id = :id", requestId);
    }

    public Optional<InformationDraftView> lock(String requestId) {
        return query(" WHERE request_id = :id FOR UPDATE", requestId);
    }

    /** CAS по draftVersion; переход в SUBMITTED атомарен с проверкой версии. */
    public boolean advance(String requestId, long expectedDraftVersion, String state, Instant now) {
        return jdbc.sql("""
                        UPDATE applications.information_draft
                        SET draft_version = draft_version + 1, state = :state, updated_at = :now
                        WHERE request_id = :id AND draft_version = :expected AND state = 'EDITING'
                        """)
                .param("state", state).param("now", Timestamp.from(now)).param("id", requestId)
                .param("expected", expectedDraftVersion)
                .update() == 1;
    }

    private Optional<InformationDraftView> query(String where, String requestId) {
        return jdbc.sql("""
                        SELECT request_id, application_id, company_id, request_version, draft_version,
                               requirements_version, base_statement_version, requested_fields, state
                        FROM applications.information_draft
                        """ + where)
                .param("id", requestId)
                .query((rs, row) -> new InformationDraftView(
                        rs.getString("request_id"), rs.getString("application_id"), rs.getString("company_id"),
                        rs.getLong("request_version"), rs.getLong("draft_version"), rs.getLong("requirements_version"),
                        rs.getLong("base_statement_version"),
                        List.copyOf(Arrays.stream((Object[]) rs.getArray("requested_fields").getArray())
                                .map(String.class::cast).toList()),
                        rs.getString("state")))
                .optional();
    }
}
