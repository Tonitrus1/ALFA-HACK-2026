package ru.alfahack.credit.integration.application;

import java.time.Instant;
import java.util.List;

/** Решение симулятора по версии дела; MANUAL — внутреннее, клиенту не показывается как решение. */
public record DecisionView(
        String decisionId, String caseId, String applicationId, long caseVersion, String outcome,
        String publicExplanation, String policyVersion, List<String> reasonCodes, String riskInferenceId,
        String riskMode, String financialSnapshotId, List<String> offerIds, Instant createdAt) {

    public DecisionView {
        reasonCodes = List.copyOf(reasonCodes);
        offerIds = List.copyOf(offerIds);
    }
}
