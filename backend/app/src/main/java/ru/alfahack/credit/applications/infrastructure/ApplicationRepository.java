package ru.alfahack.credit.applications.infrastructure;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;
import java.util.Optional;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

import ru.alfahack.credit.applications.application.ApplicationView;
import ru.alfahack.credit.applications.application.BusinessData;

@Repository
public class ApplicationRepository {

    private static final String SELECT = """
            SELECT application_id, company_id, product_id, product_version, status, version, purpose, amount_minor,
                   term_months, business_annual_revenue_minor, business_annual_expenses_minor,
                   business_current_debt_minor, business_age_months, business_activity_description,
                   business_source_confirmation_version, financial_statement_version, financial_snapshot_id,
                   created_by, create_key, create_body_digest, created_at, updated_at
            FROM applications.application
            """;

    private final JdbcClient jdbc;

    public ApplicationRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    public Optional<ApplicationView> find(String applicationId) {
        return jdbc.sql(SELECT + " WHERE application_id = :id")
                .param("id", applicationId)
                .query((rs, row) -> map(rs))
                .optional();
    }

    /** Блокирует строку заявки до конца транзакции команды. */
    public Optional<ApplicationView> lock(String applicationId) {
        return jdbc.sql(SELECT + " WHERE application_id = :id FOR UPDATE")
                .param("id", applicationId)
                .query((rs, row) -> map(rs))
                .optional();
    }

    public Optional<ApplicationView> findByCreateKey(String actorId, String companyId, String createKey) {
        return jdbc.sql(SELECT + " WHERE created_by = :actor AND company_id = :company AND create_key = :key")
                .param("actor", actorId)
                .param("company", companyId)
                .param("key", createKey)
                .query((rs, row) -> map(rs))
                .optional();
    }

    /** Keyset-страница: (updated_at DESC, application_id DESC) строго после курсора. */
    public List<ApplicationView> list(String companyId, Instant afterUpdatedAt, String afterId, int limit) {
        return jdbc.sql(SELECT + """
                        WHERE company_id = :company
                          AND (CAST(:afterUpdatedAt AS timestamptz) IS NULL
                               OR (updated_at, application_id) < (CAST(:afterUpdatedAt AS timestamptz), :afterId))
                        ORDER BY updated_at DESC, application_id DESC
                        LIMIT :limit
                        """)
                .param("company", companyId)
                .param("afterUpdatedAt", afterUpdatedAt == null ? null : Timestamp.from(afterUpdatedAt))
                .param("afterId", afterId)
                .param("limit", limit)
                .query((rs, row) -> map(rs))
                .list();
    }

    /** INSERT по уникальному (created_by, company_id, create_key); false — ключ уже занят. */
    public boolean insertIfAbsent(ApplicationView application) {
        BusinessData business = application.business();
        return jdbc.sql("""
                        INSERT INTO applications.application (
                            application_id, company_id, product_id, product_version, status, version, purpose,
                            amount_minor, term_months, business_annual_revenue_minor, business_annual_expenses_minor,
                            business_current_debt_minor, business_age_months, business_activity_description,
                            business_source_confirmation_version, created_by, create_key, create_body_digest,
                            created_at, updated_at)
                        VALUES (:id, :company, :product, :productVersion, :status, :version, :purpose, :amount, :term,
                                :revenue, :expenses, :debt, :age, :activity, :sourceVersion, :createdBy, :createKey,
                                :createDigest, :createdAt, :updatedAt)
                        ON CONFLICT (created_by, company_id, create_key) DO NOTHING
                        """)
                .param("id", application.applicationId())
                .param("company", application.companyId())
                .param("product", application.productId())
                .param("productVersion", application.productVersion())
                .param("status", application.status())
                .param("version", application.version())
                .param("purpose", application.purpose())
                .param("amount", application.amountMinor())
                .param("term", application.termMonths())
                .param("revenue", business.annualRevenueMinor())
                .param("expenses", business.annualExpensesMinor())
                .param("debt", business.currentDebtMinor())
                .param("age", business.businessAgeMonths())
                .param("activity", business.activityDescription())
                .param("sourceVersion", business.sourceConfirmationVersion())
                .param("createdBy", application.createdBy())
                .param("createKey", application.createKey())
                .param("createDigest", application.createBodyDigest())
                .param("createdAt", Timestamp.from(application.createdAt()))
                .param("updatedAt", Timestamp.from(application.updatedAt()))
                .update() == 1;
    }

    /** CAS-сохранение условий черновика; false — версия изменилась или заявка уже не DRAFT. */
    public boolean updateDraft(ApplicationView draft, long expectedVersion, Instant now) {
        BusinessData business = draft.business();
        return jdbc.sql("""
                        UPDATE applications.application
                        SET purpose = :purpose, amount_minor = :amount, term_months = :term,
                            business_annual_revenue_minor = :revenue, business_annual_expenses_minor = :expenses,
                            business_current_debt_minor = :debt, business_age_months = :age,
                            business_activity_description = :activity,
                            business_source_confirmation_version = :sourceVersion,
                            version = version + 1, updated_at = :now
                        WHERE application_id = :id AND version = :expectedVersion AND status = 'DRAFT'
                        """)
                .param("purpose", draft.purpose())
                .param("amount", draft.amountMinor())
                .param("term", draft.termMonths())
                .param("revenue", business.annualRevenueMinor())
                .param("expenses", business.annualExpensesMinor())
                .param("debt", business.currentDebtMinor())
                .param("age", business.businessAgeMonths())
                .param("activity", business.activityDescription())
                .param("sourceVersion", business.sourceConfirmationVersion())
                .param("now", Timestamp.from(now))
                .param("id", draft.applicationId())
                .param("expectedVersion", expectedVersion)
                .update() == 1;
    }

    /** Версия контейнера (ETag) растёт при изменении финансовой формы черновика. */
    public boolean bumpVersion(String applicationId, long expectedVersion, Instant now) {
        return jdbc.sql("""
                        UPDATE applications.application SET version = version + 1, updated_at = :now
                        WHERE application_id = :id AND version = :expectedVersion AND status = 'DRAFT'
                        """)
                .param("now", Timestamp.from(now))
                .param("id", applicationId)
                .param("expectedVersion", expectedVersion)
                .update() == 1;
    }

    public boolean markSubmitted(
            String applicationId, long expectedVersion, long financialStatementVersion, String financialSnapshotId,
            Instant now) {
        return jdbc.sql("""
                        UPDATE applications.application
                        SET status = 'SUBMITTED', version = version + 1, financial_statement_version = :statementVersion,
                            financial_snapshot_id = :snapshotId, updated_at = :now
                        WHERE application_id = :id AND version = :expectedVersion AND status = 'DRAFT'
                        """)
                .param("statementVersion", financialStatementVersion)
                .param("snapshotId", financialSnapshotId)
                .param("now", Timestamp.from(now))
                .param("id", applicationId)
                .param("expectedVersion", expectedVersion)
                .update() == 1;
    }

    private static ApplicationView map(ResultSet rs) throws SQLException {
        return new ApplicationView(
                rs.getString("application_id"),
                rs.getString("company_id"),
                rs.getString("product_id"),
                rs.getLong("product_version"),
                rs.getString("status"),
                rs.getLong("version"),
                rs.getString("purpose"),
                rs.getLong("amount_minor"),
                rs.getInt("term_months"),
                new BusinessData(
                        rs.getObject("business_annual_revenue_minor", Long.class),
                        rs.getObject("business_annual_expenses_minor", Long.class),
                        rs.getObject("business_current_debt_minor", Long.class),
                        rs.getObject("business_age_months", Long.class),
                        rs.getString("business_activity_description"),
                        rs.getString("business_source_confirmation_version")),
                rs.getObject("financial_statement_version", Long.class),
                rs.getString("financial_snapshot_id"),
                rs.getString("created_by"),
                rs.getString("create_key"),
                rs.getString("create_body_digest"),
                rs.getTimestamp("created_at").toInstant(),
                rs.getTimestamp("updated_at").toInstant());
    }
}
