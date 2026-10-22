package ru.alfahack.credit.applications.application;

import java.util.Map;
import java.util.Optional;

import org.springframework.stereotype.Service;

import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.json.JsonMapper;

import ru.alfahack.credit.applications.infrastructure.ApplicationRepository;
import ru.alfahack.credit.applications.infrastructure.FinancialStatementRepository;
import ru.alfahack.credit.applications.infrastructure.SubmissionSnapshotRepository;

/**
 * Чтение отправленных пакетов и неизменяемых финансовых снимков для банковского симулятора и ML-адаптера.
 * Только по точному идентификатору; «последняя анкета компании» не читается.
 */
@Service
public class SubmissionQueries {

    private static final TypeReference<Map<String, Object>> MAP = new TypeReference<>() {
    };

    public record SubmittedApplication(
            ApplicationView application, String submissionSnapshotId, long submissionVersion) {
    }

    public record FinancialSnapshotData(
            String financialSnapshotId, String applicationId, String companyId, long statementVersion,
            String digest, Map<String, Object> statement, FinancialValues values, java.time.Instant createdAt) {
    }

    private final ApplicationRepository applications;
    private final SubmissionSnapshotRepository submissions;
    private final FinancialStatementRepository statements;
    private final JsonMapper json;

    public SubmissionQueries(ApplicationRepository applications, SubmissionSnapshotRepository submissions,
                             FinancialStatementRepository statements, JsonMapper json) {
        this.applications = applications;
        this.submissions = submissions;
        this.statements = statements;
        this.json = json;
    }

    public Optional<SubmittedApplication> submitted(String applicationId) {
        return applications.find(applicationId)
                .filter(application -> !"DRAFT".equals(application.status()))
                .flatMap(application -> submissions.latest(applicationId)
                        .map(ref -> new SubmittedApplication(application, ref.snapshotId(), ref.version())));
    }

    public Optional<FinancialSnapshotData> financialSnapshot(String financialSnapshotId) {
        return statements.snapshot(financialSnapshotId).map(row -> {
            Map<String, Object> statement = json.readValue(row.statementJson(), MAP);
            return new FinancialSnapshotData(row.financialSnapshotId(), row.applicationId(), row.companyId(),
                    row.statementVersion(), row.digest(), statement, values(statement), row.createdAt());
        });
    }

    @SuppressWarnings("unchecked")
    private static FinancialValues values(Map<String, Object> statement) {
        Map<String, Object> values = (Map<String, Object>) statement.getOrDefault("values", Map.of());
        return new FinancialValues(
                number(values, FinancialField.TOTAL_ASSETS), number(values, FinancialField.TOTAL_LIABILITIES),
                number(values, FinancialField.CURRENT_ASSETS), number(values, FinancialField.CURRENT_LIABILITIES),
                number(values, FinancialField.EQUITY), number(values, FinancialField.REVENUE),
                number(values, FinancialField.NET_PROFIT), number(values, FinancialField.EBIT));
    }

    private static Long number(Map<String, Object> values, FinancialField field) {
        Object value = values.get(field.wireName());
        return value instanceof Number n ? n.longValue() : null;
    }
}
