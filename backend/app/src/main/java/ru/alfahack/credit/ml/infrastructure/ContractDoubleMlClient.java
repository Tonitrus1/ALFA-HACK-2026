package ru.alfahack.credit.ml.infrastructure;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import ru.alfahack.credit.ml.application.MlClient;
import ru.alfahack.credit.ml.application.MlContracts;
import ru.alfahack.credit.platform.support.Digests;

/**
 * Контрактный двойник ML (не модель): отвечает по тем же схемам детерминированно, чтобы backend и UI работали
 * до готовности моделей. Score — простая демонстрационная формула по долговой нагрузке и прибыли; помечается
 * releaseId=contract-double и режимом CONTRACT_DOUBLE в записи инференса. Ранжирование — RULES, RAG —
 * INSUFFICIENT_EVIDENCE без выдуманного ответа. Готовым MVP считается только прогон с настоящими моделями.
 */
class ContractDoubleMlClient implements MlClient {

    static final String RELEASE = "contract-double";
    static final String ZERO_DIGEST = "0".repeat(64);

    /** Признаки выданных снимков; после перезапуска неизвестный снимок даёт сбой риска (→ MANUAL). */
    private final Map<String, Map<String, Double>> snapshots = new ConcurrentHashMap<>();

    @Override
    public String mode() {
        return "CONTRACT_DOUBLE";
    }

    @Override
    public MlContracts.FeatureSnapshot createFeatureSnapshot(
            String idempotencyKey, MlContracts.FeatureSnapshotInput input) {
        Map<String, Object> values = values(input.financialStatement());
        Map<String, Double> features = new LinkedHashMap<>();
        double assets = number(values, "totalAssetsMinor");
        features.put("X1", ratio(number(values, "currentAssetsMinor") - number(values, "currentLiabilitiesMinor"), assets));
        features.put("X2", ratio(number(values, "netProfitMinor"), assets));
        features.put("X3", ratio(number(values, "ebitMinor"), assets));
        features.put("X4", ratio(number(values, "equityMinor"), number(values, "totalLiabilitiesMinor")));
        features.put("X7", ratio(number(values, "revenueMinor"), assets));
        features.put("X8", ratio(number(values, "totalLiabilitiesMinor"), assets));
        features.put("X9", ratio(number(values, "currentAssetsMinor"), number(values, "currentLiabilitiesMinor")));
        features.put("X10", ratio(number(values, "equityMinor"), assets));
        List<String> missing = features.entrySet().stream().filter(e -> e.getValue() == null).map(Map.Entry::getKey)
                .toList();
        String digest = Digests.sha256(input.financialSnapshotDigest() + "|" + features);
        String featureSnapshotId = "fs-" + digest.substring(0, 32);
        snapshots.put(featureSnapshotId, features);
        return new MlContracts.FeatureSnapshot(featureSnapshotId, input.submissionSnapshotId(),
                input.financialStatementVersion(), 2, ZERO_DIGEST, input.asOf(), input.asOf(), features, missing,
                digest, input.financialSnapshotId(), input.financialSnapshotDigest());
    }

    @Override
    public MlContracts.RiskResult evaluateRisk(String idempotencyKey, MlContracts.RiskRequest request) {
        Map<String, Double> features = snapshots.get(request.featureSnapshotId());
        if (features == null) {
            throw new IllegalStateException("Unknown feature snapshot");
        }
        double score = demonstrationScore(features);
        return new MlContracts.RiskResult("inf-" + Digests.sha256(request.requestId()).substring(0, 32),
                request.requestId(), score, "BANKRUPTCY_PROXY", "DEMONSTRATION", RELEASE, ZERO_DIGEST,
                "contract-double/1", request.featureSnapshotId(), request.featureSnapshotDigest(),
                List.of("CONTRACT_DOUBLE"));
    }

    @Override
    public MlContracts.RankingResult rank(String idempotencyKey, MlContracts.RankingRequest request) {
        return new MlContracts.RankingResult(request.requestId(), request.scope(), request.candidateIds(),
                request.candidateSetDigest(), "exposure-" + request.requestId(), RELEASE, "RULES", "DEFAULT_ORDER");
    }

    @Override
    public MlContracts.AssistantResponse answer(MlContracts.RagInput input) {
        return new MlContracts.AssistantResponse(
                input.conversationId() != null ? input.conversationId() : "conv-" + input.requestId(),
                "msg-" + input.requestId(), "INSUFFICIENT_EVIDENCE", "", List.of(), RELEASE, ZERO_DIGEST,
                input.kbEpoch());
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> values(Map<String, Object> statement) {
        Object values = statement.get("values");
        return values instanceof Map<?, ?> map ? (Map<String, Object>) map : Map.of();
    }

    private static double number(Map<String, Object> values, String field) {
        Object value = values.get(field);
        return value instanceof Number n ? n.doubleValue() : Double.NaN;
    }

    private static Double ratio(double numerator, double denominator) {
        if (Double.isNaN(numerator) || Double.isNaN(denominator) || denominator == 0) {
            return null;
        }
        return BigDecimal.valueOf(numerator / denominator).setScale(6, RoundingMode.HALF_UP).doubleValue();
    }

    /** 0,05 + 0,5 × liabilities/assets + 0,25 при убытке, в пределах [0, 1]. Не PD. */
    static double demonstrationScore(Map<String, Double> features) {
        double leverage = features.get("X8") == null ? 1.0 : features.get("X8");
        double loss = features.get("X2") != null && features.get("X2") < 0 ? 0.25 : 0.0;
        double score = Math.max(0, Math.min(1, 0.05 + 0.5 * leverage + loss));
        return BigDecimal.valueOf(score).setScale(6, RoundingMode.HALF_UP).doubleValue();
    }
}
