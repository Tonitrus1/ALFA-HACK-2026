package ru.alfahack.credit.integration.infrastructure;

import java.sql.Array;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.Arrays;
import java.util.List;
import java.util.Optional;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

import ru.alfahack.credit.integration.application.DecisionView;
import ru.alfahack.credit.integration.application.OfferView;

@Repository
public class DecisionRepository {

    private final JdbcClient jdbc;

    public DecisionRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    public void insertDecision(DecisionView decision) {
        jdbc.sql("""
                        INSERT INTO integration.decision (decision_id, case_id, application_id, case_version, outcome,
                            public_explanation, policy_version, reason_codes, risk_inference_id, risk_mode,
                            financial_snapshot_id, created_at)
                        VALUES (:id, :case, :application, :version, :outcome, :explanation, :policy, :reasons,
                                :inference, :riskMode, :snapshot, :now)
                        """)
                .param("id", decision.decisionId()).param("case", decision.caseId())
                .param("application", decision.applicationId()).param("version", decision.caseVersion())
                .param("outcome", decision.outcome()).param("explanation", decision.publicExplanation())
                .param("policy", decision.policyVersion()).param("reasons", decision.reasonCodes().toArray(String[]::new))
                .param("inference", decision.riskInferenceId()).param("riskMode", decision.riskMode())
                .param("snapshot", decision.financialSnapshotId()).param("now", Timestamp.from(decision.createdAt()))
                .update();
    }

    public void insertOffer(OfferView offer, Instant now) {
        jdbc.sql("""
                        INSERT INTO integration.offer (offer_id, decision_id, application_id, company_id, version,
                            status, amount_minor, term_months, terms_disclosure, valid_until, created_at)
                        VALUES (:id, :decision, :application, :company, :version, :status, :amount, :term,
                                :disclosure, :validUntil, :now)
                        """)
                .param("id", offer.offerId()).param("decision", offer.decisionId())
                .param("application", offer.applicationId()).param("company", offer.companyId())
                .param("version", offer.version()).param("status", offer.status())
                .param("amount", offer.amountMinor()).param("term", offer.termMonths())
                .param("disclosure", offer.termsDisclosure()).param("validUntil", Timestamp.from(offer.validUntil()))
                .param("now", Timestamp.from(now))
                .update();
    }

    public Optional<DecisionView> latestForApplication(String applicationId) {
        return jdbc.sql("""
                        SELECT d.*, coalesce(array_agg(o.offer_id ORDER BY o.offer_id)
                                             FILTER (WHERE o.offer_id IS NOT NULL), '{}') AS offer_ids
                        FROM integration.decision d LEFT JOIN integration.offer o ON o.decision_id = d.decision_id
                        WHERE d.application_id = :application
                        GROUP BY d.decision_id
                        ORDER BY d.case_version DESC LIMIT 1
                        """)
                .param("application", applicationId)
                .query((rs, row) -> decision(rs))
                .optional();
    }

    public Optional<OfferView> offer(String offerId) {
        return jdbc.sql("""
                        SELECT offer_id, decision_id, application_id, company_id, version, status, amount_minor,
                               term_months, terms_disclosure, valid_until
                        FROM integration.offer WHERE offer_id = :id
                        """)
                .param("id", offerId)
                .query((rs, row) -> new OfferView(rs.getString("offer_id"), rs.getString("decision_id"),
                        rs.getString("application_id"), rs.getString("company_id"), rs.getLong("version"),
                        rs.getString("status"), rs.getLong("amount_minor"), rs.getInt("term_months"),
                        rs.getString("terms_disclosure"), rs.getTimestamp("valid_until").toInstant()))
                .optional();
    }

    private static DecisionView decision(ResultSet rs) throws SQLException {
        return new DecisionView(rs.getString("decision_id"), rs.getString("case_id"), rs.getString("application_id"),
                rs.getLong("case_version"), rs.getString("outcome"), rs.getString("public_explanation"),
                rs.getString("policy_version"), strings(rs.getArray("reason_codes")), rs.getString("risk_inference_id"),
                rs.getString("risk_mode"), rs.getString("financial_snapshot_id"), strings(rs.getArray("offer_ids")),
                rs.getTimestamp("created_at").toInstant());
    }

    private static List<String> strings(Array array) throws SQLException {
        return Arrays.stream((Object[]) array.getArray()).map(String.class::cast).toList();
    }
}
