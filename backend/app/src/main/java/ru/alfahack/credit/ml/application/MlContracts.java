package ru.alfahack.credit.ml.application;

import java.time.Instant;
import java.util.List;
import java.util.Map;

/** Wire-DTO внутреннего ML API v2 (internal.openapi: MLFeatureSnapshot*, MLRisk*, MLRanking*, MLRagInput). */
public final class MlContracts {

    private MlContracts() {
    }

    public record FeatureSnapshotInput(
            String applicationId, String submissionSnapshotId, long financialStatementVersion, Instant asOf,
            String purpose, String financialSnapshotId, String financialSnapshotDigest,
            Map<String, Object> financialStatement, Instant latestSourceAvailableAt) {
        public FeatureSnapshotInput(String app, String submission, long version, Instant asOf, String purpose,
                String financial, String digest, Map<String,Object> statement) {
            this(app, submission, version, asOf, purpose, financial, digest, statement, null);
        }
    }

    public record FeatureSnapshot(
            String featureSnapshotId, String submissionSnapshotId, long financialStatementVersion,
            int featureSchemaVersion, String featureCodeDigest, Instant featureAsOf, Instant latestSourceAvailableAt,
            Map<String, Double> features, List<String> missingFeatures, String snapshotDigest,
            String financialSnapshotId, String financialSnapshotDigest) {
    }

    public record RiskRequest(
            String requestId, String featureSnapshotId, String featureSnapshotDigest, int featureSchemaVersion,
            String purpose) {
    }

    public record RiskResult(
            String inferenceId, String requestId, double score, String scoreKind, String calibrationStatus,
            String releaseId, String bundleDigest, String modelVersion, String featureSnapshotId,
            String featureSnapshotDigest, List<String> internalReasonCodes) {
    }

    public record CandidateText(String itemId, String text) {
    }

    public record RankingRequest(
            String requestId, String scope, List<String> candidateIds, String candidateSetDigest, long catalogVersion,
            Long eligibilityVersion, String stage, String contextCategory, String fundingPurpose, String contextText,
            List<CandidateText> candidateTexts) {
    }

    public record RankingResult(
            String requestId, String scope, List<String> rankedIds, String candidateSetDigest, String exposureId,
            String releaseId, String mode, String reasonCategory) {
    }

    public record AllowedSource(String documentId, long documentVersion) {
    }

    public record RagInput(
            String requestId, String companyId, String subjectRef, String message, String conversationId,
            long kbEpoch, List<AllowedSource> allowedSources) {
    }

    public record Citation(
            String documentId, long documentVersion, String chunkId, String title, String locator,
            String sourcePath) {
    }

    public record AssistantResponse(
            String conversationId, String messageId, String status, String answer, List<Citation> citations,
            String releaseId, String bundleDigest, long kbEpoch) {
    }
}
