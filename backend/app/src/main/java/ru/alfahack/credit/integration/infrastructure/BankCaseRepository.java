package ru.alfahack.credit.integration.infrastructure;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.Optional;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

import ru.alfahack.credit.integration.application.BankCaseView;

@Repository
public class BankCaseRepository {

    private final JdbcClient jdbc;

    public BankCaseRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    /** Дедуп по externalRequestId и applicationId: повторный запрос дела не создаёт второе. */
    public boolean insertIfAbsent(BankCaseView bankCase) {
        return jdbc.sql("""
                        INSERT INTO integration.bank_case (case_id, application_id, company_id, external_request_id,
                                                           case_version, status, created_at, updated_at,
                                                           financial_snapshot_id)
                        VALUES (:id, :application, :company, :external, :version, :status, :createdAt, :updatedAt,
                                :financialSnapshot)
                        ON CONFLICT DO NOTHING
                        """)
                .param("id", bankCase.caseId())
                .param("application", bankCase.applicationId())
                .param("company", bankCase.companyId())
                .param("external", bankCase.externalRequestId())
                .param("version", bankCase.caseVersion())
                .param("status", bankCase.status())
                .param("createdAt", Timestamp.from(bankCase.createdAt()))
                .param("updatedAt", Timestamp.from(bankCase.updatedAt()))
                .param("financialSnapshot", bankCase.financialSnapshotId())
                .update() == 1;
    }

    public Optional<BankCaseView> findByApplication(String applicationId) {
        return query("application_id = :key", applicationId);
    }

    public Optional<BankCaseView> find(String caseId) {
        return query("case_id = :key", caseId);
    }

    /** CAS банковского дела: переход только из ожидаемого статуса и версии; caseVersion монотонно растёт. */
    public boolean transition(String caseId, long expectedVersion, String fromStatus, String toStatus,
                              String financialSnapshotId, Instant now) {
        return jdbc.sql("""
                        UPDATE integration.bank_case
                        SET status = :to, case_version = case_version + 1, updated_at = :now,
                            financial_snapshot_id = COALESCE(:snapshot, financial_snapshot_id)
                        WHERE case_id = :id AND case_version = :version AND status = :from
                        """)
                .param("to", toStatus).param("now", Timestamp.from(now)).param("snapshot", financialSnapshotId)
                .param("id", caseId).param("version", expectedVersion).param("from", fromStatus)
                .update() == 1;
    }

    private Optional<BankCaseView> query(String condition, String key) {
        return jdbc.sql("""
                        SELECT case_id, application_id, company_id, external_request_id, case_version, status,
                               created_at, updated_at, financial_snapshot_id
                        FROM integration.bank_case WHERE
                        """ + " " + condition)
                .param("key", key)
                .query((rs, row) -> new BankCaseView(
                        rs.getString("case_id"),
                        rs.getString("application_id"),
                        rs.getString("company_id"),
                        rs.getString("external_request_id"),
                        rs.getLong("case_version"),
                        rs.getString("status"),
                        rs.getTimestamp("created_at").toInstant(),
                        rs.getTimestamp("updated_at").toInstant(),
                        rs.getString("financial_snapshot_id")))
                .optional();
    }
}
