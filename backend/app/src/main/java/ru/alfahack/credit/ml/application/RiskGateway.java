package ru.alfahack.credit.ml.application;

import java.time.Clock;
import java.time.Instant;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import ru.alfahack.credit.ml.infrastructure.InferenceRepository;
import ru.alfahack.credit.platform.support.Times;

/**
 * Риск по точному неизменяемому финансовому снимку: feature snapshot → evaluation. Ответ проверяется
 * (тот же снимок и digest, score в [0,1], согласованные scoreKind/calibration), запись инференса фиксируется
 * до использования. Любой сбой (таймаут, ошибка, несовпадение, отказ записи) — пусто: политика даёт MANUAL.
 */
@Service
public class RiskGateway {

    private static final Logger log = LoggerFactory.getLogger(RiskGateway.class);
    static final String PURPOSE = "DEMO_RESEARCH";
    static final Set<String> SCORE_KINDS = Set.of("BANKRUPTCY_PROXY", "PD");

    public record RiskInput(
            String applicationId, String submissionSnapshotId, String financialSnapshotId,
            String financialSnapshotDigest, long financialStatementVersion, Map<String, Object> financialStatement) {
    }

    private final MlClient client;
    private final InferenceRepository inferences;
    private final Clock clock;

    public RiskGateway(MlClient client, InferenceRepository inferences, Clock clock) {
        this.client = client;
        this.inferences = inferences;
        this.clock = clock;
    }

    public Optional<RiskAssessment> assess(RiskInput input) {
        try {
            Instant now = Times.now(clock);
            String key = "risk:" + input.financialSnapshotId();
            MlContracts.FeatureSnapshot features = client.createFeatureSnapshot(key + ":features",
                    new MlContracts.FeatureSnapshotInput(input.applicationId(), input.submissionSnapshotId(),
                            input.financialStatementVersion(), now, PURPOSE, input.financialSnapshotId(),
                            input.financialSnapshotDigest(), input.financialStatement()));
            if (!input.financialSnapshotId().equals(features.financialSnapshotId())
                    || !input.financialSnapshotDigest().equals(features.financialSnapshotDigest())
                    || features.featureSchemaVersion() != 2) {
                log.warn("Feature snapshot mismatch applicationId={}", input.applicationId());
                return Optional.empty();
            }
            MlContracts.RiskResult result = client.evaluateRisk(key + ":evaluation", new MlContracts.RiskRequest(
                    key, features.featureSnapshotId(), features.snapshotDigest(), 2, PURPOSE));
            if (!valid(result, features, key)) {
                log.warn("Risk result rejected applicationId={}", input.applicationId());
                return Optional.empty();
            }
            inferences.insert(result, input.applicationId(), input.financialSnapshotId(), client.mode(), now);
            return Optional.of(new RiskAssessment(result.inferenceId(), result.score(), result.scoreKind(),
                    result.releaseId(), result.modelVersion(), client.mode()));
        } catch (RuntimeException e) {
            log.warn("Risk unavailable applicationId={} error={}", input.applicationId(), e.getClass().getSimpleName());
            return Optional.empty();
        }
    }

    private static boolean valid(MlContracts.RiskResult result, MlContracts.FeatureSnapshot features, String key) {
        boolean calibrated = ("BANKRUPTCY_PROXY".equals(result.scoreKind())
                && "DEMONSTRATION".equals(result.calibrationStatus()))
                || ("PD".equals(result.scoreKind()) && "VALIDATED".equals(result.calibrationStatus()));
        return result.inferenceId() != null
                && key.equals(result.requestId())
                && features.featureSnapshotId().equals(result.featureSnapshotId())
                && features.snapshotDigest().equals(result.featureSnapshotDigest())
                && result.score() >= 0 && result.score() <= 1 && !Double.isNaN(result.score())
                && SCORE_KINDS.contains(result.scoreKind())
                && calibrated;
    }
}
