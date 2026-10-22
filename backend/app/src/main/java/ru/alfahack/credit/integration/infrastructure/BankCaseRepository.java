package ru.alfahack.credit.integration.infrastructure;

import java.sql.Timestamp;
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
                                                           case_version, status, created_at, updated_at)
                        VALUES (:id, :application, :company, :external, :version, :status, :createdAt, :updatedAt)
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
                .update() == 1;
    }

    public Optional<BankCaseView> findByApplication(String applicationId) {
        return jdbc.sql("""
                        SELECT case_id, application_id, company_id, external_request_id, case_version, status,
                               created_at, updated_at
                        FROM integration.bank_case WHERE application_id = :application
                        """)
                .param("application", applicationId)
                .query((rs, row) -> new BankCaseView(
                        rs.getString("case_id"),
                        rs.getString("application_id"),
                        rs.getString("company_id"),
                        rs.getString("external_request_id"),
                        rs.getLong("case_version"),
                        rs.getString("status"),
                        rs.getTimestamp("created_at").toInstant(),
                        rs.getTimestamp("updated_at").toInstant()))
                .optional();
    }
}
