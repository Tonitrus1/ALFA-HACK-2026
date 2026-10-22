package ru.alfahack.credit.applications.infrastructure;

import java.sql.Date;
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

import ru.alfahack.credit.applications.application.ApplicationCommands;
import ru.alfahack.credit.applications.application.FinancialField;
import ru.alfahack.credit.applications.application.FinancialStatementView;
import ru.alfahack.credit.applications.application.FinancialStatementView.FieldProvenance;
import ru.alfahack.credit.applications.application.FinancialValues;

@Repository
public class FinancialStatementRepository {

    private static final TypeReference<List<ApplicationCommands.DocumentReference>> REFERENCES = new TypeReference<>() {
    };

    private final JdbcClient jdbc;
    private final JsonMapper json;

    public FinancialStatementRepository(JdbcClient jdbc, JsonMapper json) {
        this.jdbc = jdbc;
        this.json = json;
    }

    public Optional<FinancialStatementView> find(String applicationId, long containerVersion) {
        return findContainer(applicationId, containerVersion);
    }

    /** Форма контейнера: исходной анкеты (containerId = applicationId) или черновика RFI (= requestId). */
    public Optional<FinancialStatementView> findContainer(String containerId, long containerVersion) {
        return jdbc.sql("""
                        SELECT application_id, statement_version, period_start, period_end, reporting_standard, currency,
                               total_assets_minor, total_liabilities_minor, current_assets_minor,
                               current_liabilities_minor, equity_minor, revenue_minor, net_profit_minor, ebit_minor,
                               source_document_references::text AS refs, confirmed, updated_at
                        FROM applications.financial_statement WHERE container_id = :id
                        """)
                .param("id", containerId)
                .query((rs, row) -> map(rs, containerVersion))
                .optional()
                .map(statement -> new FinancialStatementView(
                        statement.applicationId(), statement.statementVersion(), statement.containerVersion(),
                        statement.periodStart(), statement.periodEnd(), statement.reportingStandard(),
                        statement.currency(), statement.values(), statement.sourceDocumentReferences(),
                        statement.confirmed(),
                        statement.confirmed()
                                ? provenance(statement.applicationId(), statement.statementVersion())
                                : List.of(),
                        statement.updatedAt()));
    }

    /** Новая версия содержимого: подтверждение всегда сбрасывается. */
    public void upsert(String applicationId, long statementVersion, FinancialStatementView.Content content,
                       String referencesJson, Instant now) {
        upsertContainer(applicationId, applicationId, statementVersion, content, referencesJson, false, now);
    }

    public void upsertContainer(String containerId, String applicationId, long statementVersion,
                                FinancialStatementView.Content content, String referencesJson, boolean confirmed,
                                Instant now) {
        FinancialValues values = content.values();
        jdbc.sql("""
                        INSERT INTO applications.financial_statement (
                            container_id, application_id, statement_version, period_start, period_end, reporting_standard, currency,
                            total_assets_minor, total_liabilities_minor, current_assets_minor, current_liabilities_minor,
                            equity_minor, revenue_minor, net_profit_minor, ebit_minor, source_document_references,
                            confirmed, updated_at)
                        VALUES (:container, :id, :version, :start, :end, :standard, :currency, :ta, :tl, :ca, :cl, :eq,
                                :rev, :np, :ebit, CAST(:refs AS jsonb), :confirmed, :now)
                        ON CONFLICT (container_id) DO UPDATE SET
                            statement_version = EXCLUDED.statement_version, period_start = EXCLUDED.period_start,
                            period_end = EXCLUDED.period_end, reporting_standard = EXCLUDED.reporting_standard,
                            currency = EXCLUDED.currency, total_assets_minor = EXCLUDED.total_assets_minor,
                            total_liabilities_minor = EXCLUDED.total_liabilities_minor,
                            current_assets_minor = EXCLUDED.current_assets_minor,
                            current_liabilities_minor = EXCLUDED.current_liabilities_minor,
                            equity_minor = EXCLUDED.equity_minor, revenue_minor = EXCLUDED.revenue_minor,
                            net_profit_minor = EXCLUDED.net_profit_minor, ebit_minor = EXCLUDED.ebit_minor,
                            source_document_references = EXCLUDED.source_document_references,
                            confirmed = false, updated_at = EXCLUDED.updated_at
                        """)
                .param("container", containerId)
                .param("id", applicationId)
                .param("version", statementVersion)
                .param("confirmed", confirmed)
                .param("start", Date.valueOf(content.periodStart()))
                .param("end", Date.valueOf(content.periodEnd()))
                .param("standard", content.reportingStandard())
                .param("currency", content.currency())
                .param("ta", values.totalAssetsMinor())
                .param("tl", values.totalLiabilitiesMinor())
                .param("ca", values.currentAssetsMinor())
                .param("cl", values.currentLiabilitiesMinor())
                .param("eq", values.equityMinor())
                .param("rev", values.revenueMinor())
                .param("np", values.netProfitMinor())
                .param("ebit", values.ebitMinor())
                .param("refs", referencesJson)
                .param("now", Timestamp.from(now))
                .update();
    }

    /** Подтверждение версии: по одной MANUAL-provenance на каждое из 8 полей. */
    public void confirm(String applicationId, long statementVersion, String actorId, Instant now) {
        confirmContainer(applicationId, applicationId, statementVersion, actorId, now);
    }

    public void confirmContainer(String containerId, String applicationId, long statementVersion, String actorId,
                                 Instant now) {
        for (FinancialField field : FinancialField.values()) {
            jdbc.sql("""
                            INSERT INTO applications.financial_provenance
                                (application_id, statement_version, field, source_type, confirmed_by, confirmed_at)
                            VALUES (:id, :version, :field, 'MANUAL', :actor, :now)
                            ON CONFLICT DO NOTHING
                            """)
                    .param("id", applicationId)
                    .param("version", statementVersion)
                    .param("field", field.wireName())
                    .param("actor", actorId)
                    .param("now", Timestamp.from(now))
                    .update();
        }
        jdbc.sql("""
                        UPDATE applications.financial_statement SET confirmed = true, updated_at = :now
                        WHERE container_id = :container AND statement_version = :version
                        """)
                .param("now", Timestamp.from(now))
                .param("container", containerId)
                .param("version", statementVersion)
                .update();
    }

    public void insertSnapshotIfAbsent(
            String snapshotId, String applicationId, String companyId, long statementVersion, String digest,
            String statementJson, String provenanceJson, Instant now) {
        jdbc.sql("""
                        INSERT INTO applications.financial_snapshot (financial_snapshot_id, application_id, company_id,
                            statement_version, statement_digest, statement, provenance, created_at)
                        VALUES (:id, :application, :company, :version, :digest, CAST(:statement AS jsonb),
                                CAST(:provenance AS jsonb), :now)
                        ON CONFLICT (application_id, statement_version) DO NOTHING
                        """)
                .param("id", snapshotId)
                .param("application", applicationId)
                .param("company", companyId)
                .param("version", statementVersion)
                .param("digest", digest)
                .param("statement", statementJson)
                .param("provenance", provenanceJson)
                .param("now", Timestamp.from(now))
                .update();
    }

    /** Наибольшая версия формы по всем контейнерам заявки — для сквозной нумерации. */
    public long maxStatementVersion(String applicationId) {
        return jdbc.sql("SELECT coalesce(max(statement_version), 0) FROM applications.financial_statement "
                        + "WHERE application_id = :id")
                .param("id", applicationId).query(Long.class).single();
    }

    public record SnapshotRow(String financialSnapshotId, String applicationId, String companyId,
                              long statementVersion, String digest, String statementJson, Instant createdAt) {
    }

    public Optional<SnapshotRow> snapshot(String financialSnapshotId) {
        return jdbc.sql("""
                        SELECT financial_snapshot_id, application_id, company_id, statement_version, statement_digest,
                               statement::text AS statement, created_at
                        FROM applications.financial_snapshot WHERE financial_snapshot_id = :id
                        """)
                .param("id", financialSnapshotId)
                .query((rs, row) -> new SnapshotRow(rs.getString("financial_snapshot_id"),
                        rs.getString("application_id"), rs.getString("company_id"), rs.getLong("statement_version"),
                        rs.getString("statement_digest"), rs.getString("statement"), rs.getTimestamp("created_at").toInstant()))
                .optional();
    }

    public Optional<String> snapshotId(String applicationId, long statementVersion) {
        return jdbc.sql("""
                        SELECT financial_snapshot_id FROM applications.financial_snapshot
                        WHERE application_id = :application AND statement_version = :version
                        """)
                .param("application", applicationId)
                .param("version", statementVersion)
                .query(String.class)
                .optional();
    }

    private List<FieldProvenance> provenance(String applicationId, long statementVersion) {
        return jdbc.sql("""
                        SELECT field, source_type, confirmed_by, confirmed_at, extraction_id, object_version
                        FROM applications.financial_provenance
                        WHERE application_id = :id AND statement_version = :version
                        ORDER BY field
                        """)
                .param("id", applicationId)
                .param("version", statementVersion)
                .query((rs, row) -> new FieldProvenance(
                        rs.getString("field"), rs.getString("source_type"), rs.getString("confirmed_by"),
                        rs.getTimestamp("confirmed_at").toInstant(), rs.getString("extraction_id"),
                        rs.getString("object_version")))
                .list();
    }

    private FinancialStatementView map(ResultSet rs, long containerVersion) throws SQLException {
        return new FinancialStatementView(
                rs.getString("application_id"),
                rs.getLong("statement_version"),
                containerVersion,
                rs.getDate("period_start").toLocalDate(),
                rs.getDate("period_end").toLocalDate(),
                rs.getString("reporting_standard"),
                rs.getString("currency"),
                new FinancialValues(
                        rs.getObject("total_assets_minor", Long.class),
                        rs.getObject("total_liabilities_minor", Long.class),
                        rs.getObject("current_assets_minor", Long.class),
                        rs.getObject("current_liabilities_minor", Long.class),
                        rs.getObject("equity_minor", Long.class),
                        rs.getObject("revenue_minor", Long.class),
                        rs.getObject("net_profit_minor", Long.class),
                        rs.getObject("ebit_minor", Long.class)),
                json.readValue(rs.getString("refs"), REFERENCES),
                rs.getBoolean("confirmed"),
                List.of(),
                rs.getTimestamp("updated_at").toInstant());
    }
}
