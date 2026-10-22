package ru.alfahack.credit.ml.infrastructure;

import java.math.BigDecimal;
import java.sql.Timestamp;
import java.time.Instant;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

import ru.alfahack.credit.ml.application.MlContracts;

@Repository
public class InferenceRepository {

    private final JdbcClient jdbc;

    public InferenceRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    /** Повтор того же requestId не создаёт вторую запись. */
    public void insert(MlContracts.RiskResult result, String applicationId, String financialSnapshotId, String mode,
                       Instant now) {
        jdbc.sql("""
                        INSERT INTO ml.inference_record (inference_id, request_id, application_id,
                            financial_snapshot_id, feature_snapshot_id, feature_snapshot_digest, score, score_kind,
                            calibration_status, release_id, model_version, mode, created_at)
                        VALUES (:id, :request, :application, :financial, :feature, :digest, :score, :kind,
                                :calibration, :release, :model, :mode, :now)
                        ON CONFLICT (request_id) DO NOTHING
                        """)
                .param("id", result.inferenceId())
                .param("request", result.requestId())
                .param("application", applicationId)
                .param("financial", financialSnapshotId)
                .param("feature", result.featureSnapshotId())
                .param("digest", result.featureSnapshotDigest())
                .param("score", BigDecimal.valueOf(result.score()))
                .param("kind", result.scoreKind())
                .param("calibration", result.calibrationStatus())
                .param("release", result.releaseId())
                .param("model", result.modelVersion())
                .param("mode", mode)
                .param("now", Timestamp.from(now))
                .update();
    }
}
