package ru.alfahack.credit.ml.application;

/** Зафиксированный прогноз. BANKRUPTCY_PROXY — демонстрационный score, не PD. */
public record RiskAssessment(
        String inferenceId, double score, String scoreKind, String releaseId, String modelVersion, String mode) {
}
