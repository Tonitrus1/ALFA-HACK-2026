package ru.alfahack.credit.integration.application;

import java.net.http.HttpClient;
import java.sql.Timestamp;
import java.time.Clock;
import java.time.Duration;
import java.util.Map;
import java.util.Optional;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;
import ru.alfahack.credit.applications.application.SubmissionQueries;
import ru.alfahack.credit.ml.application.RiskAssessment;
import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.json.JsonMapper;

/** Backend owns immutable provenance and attempt binding; ML owns delta features and inference. */
@Service
public class FraudReviewService {
    public static final String POLICY=ru.alfahack.credit.integration.domain.SyntheticFraudPolicy.VERSION;
    private final boolean enabled;
    private final String baseUrl,token;
    private final JdbcClient jdbc;
    private final JsonMapper json;
    private final Clock clock;
    public record Result(String inferenceId,double score) {}
    public FraudReviewService(@Value("${credit.fraud.mode:off}") String mode,
            @Value("${credit.ml.base-url:}") String baseUrl,@Value("${credit.ml.service-token:}") String token,
            JdbcClient jdbc,JsonMapper json,Clock clock) {
        if(!java.util.Set.of("off","synthetic").contains(mode))throw new IllegalArgumentException("Invalid fraud mode");
        this.enabled="synthetic".equals(mode);this.baseUrl=baseUrl;this.token=token;this.jdbc=jdbc;this.json=json;this.clock=clock;
    }
    public boolean enabled(){return enabled;}
    public Optional<Result> assess(String attemptId,BankCaseView bank, SubmissionQueries.FinancialSnapshotData financial,
                                   RiskAssessment risk,Duration remaining) {
        if(!enabled || remaining.isNegative() || remaining.isZero())return Optional.empty();
        try {
            // Reuse the original reference after an interrupted/retried attempt, never select a newer source.
            var existing=jdbc.sql("SELECT * FROM integration.fraud_attempt WHERE attempt_id=:id")
                .param("id",attemptId).query().listOfRows().stream().findFirst();
            String referenceId;
            if(existing.isPresent())referenceId=existing.get().get("reference_id").toString();
            else {
                var found=jdbc.sql("SELECT reference_id FROM integration.synthetic_reference WHERE company_id=:c AND period_start=CAST(:period AS date) AND available_at<=:asof ORDER BY version DESC LIMIT 1")
                    .param("c",bank.companyId()).param("period",financial.statement().get("periodStart"))
                    .param("asof",Timestamp.from(financial.createdAt())).query(String.class).optional();
                if(found.isEmpty())return Optional.empty();
                referenceId=found.get();
            }
            Map<String,Object> reference=json.readValue(jdbc.sql("SELECT record::text FROM integration.synthetic_reference WHERE reference_id=:id AND company_id=:c")
                .param("id",referenceId).param("c",bank.companyId()).query(String.class).single(),new TypeReference<>(){});
            jdbc.sql("INSERT INTO integration.fraud_attempt(attempt_id,company_id,application_id,case_version,financial_snapshot_id,financial_digest,risk_inference_id,reference_id,reference_digest,created_at) VALUES(:id,:c,:a,:v,:s,:d,:r,:ref,:rd,:now) ON CONFLICT DO NOTHING")
                .param("id",attemptId).param("c",bank.companyId()).param("a",bank.applicationId()).param("v",bank.caseVersion())
                .param("s",financial.financialSnapshotId()).param("d",financial.digest()).param("r",risk.inferenceId())
                .param("ref",referenceId).param("rd",reference.get("recordDigest")).param("now",Timestamp.from(clock.instant())).update();
            var bound=jdbc.sql("SELECT * FROM integration.fraud_attempt WHERE attempt_id=:id").param("id",attemptId).query().singleRow();
            if(!financial.financialSnapshotId().equals(bound.get("financial_snapshot_id")) || !risk.inferenceId().equals(bound.get("risk_inference_id"))
                    || !bank.companyId().equals(bound.get("company_id")) || !financial.digest().equals(bound.get("financial_digest"))
                    || !reference.get("recordDigest").equals(bound.get("reference_digest")))return Optional.empty();
            var saved=jdbc.sql("SELECT result::text FROM integration.fraud_result WHERE attempt_id=:id").param("id",attemptId).query(String.class).optional();
            Map<String,Object> result;
            if(saved.isPresent())result=json.readValue(saved.get(),new TypeReference<>(){});
            else {
                var factory=new JdkClientHttpRequestFactory(HttpClient.newBuilder().connectTimeout(Duration.ofMillis(300)).build());
                factory.setReadTimeout(remaining.compareTo(Duration.ofSeconds(2))>0?Duration.ofSeconds(2):remaining);
                result=RestClient.builder().baseUrl(baseUrl).requestFactory(factory).defaultHeader("X-Service-Token",token).build()
                    .post().uri("/internal/compat/v1/fraud/evaluations").header("Idempotency-Key","fraud:"+attemptId)
                    .contentType(MediaType.APPLICATION_JSON).body(Map.of("companyId",bank.companyId(),"applicationId",bank.applicationId(),
                        "attemptId",attemptId,"financialSnapshotId",financial.financialSnapshotId(),"riskInferenceId",risk.inferenceId(),"reference",reference))
                    .retrieve().body(new org.springframework.core.ParameterizedTypeReference<Map<String,Object>>(){});
            }
            if(result==null || !(result.get("score") instanceof Number n) || !Double.isFinite(n.doubleValue()) || n.doubleValue()<0 || n.doubleValue()>1
                || !"SYNTHETIC_MANIPULATION_PROXY".equals(result.get("scoreKind")) || !"DEMONSTRATION".equals(result.get("calibrationStatus"))
                || !"DEMO_RESEARCH".equals(result.get("purpose")) || !"SYNTHETIC_DEMO".equals(result.get("referenceSource"))
                || !bank.companyId().equals(result.get("companyId")) || !bank.applicationId().equals(result.get("applicationId"))
                || !attemptId.equals(result.get("attemptId")) || !financial.financialSnapshotId().equals(result.get("financialSnapshotId"))
                || !financial.digest().equals(result.get("backendFinancialSnapshotDigest")) || !risk.inferenceId().equals(result.get("riskInferenceId"))
                || !reference.get("recordDigest").equals(result.get("referenceRecordDigest"))
                || !reference.get("referenceId").equals(result.get("referenceSnapshotId"))
                || !(result.get("bundleDigest") instanceof String b) || !b.matches("[0-9a-f]{64}")
                || !(result.get("inferenceId") instanceof String id) || id.isBlank())return Optional.empty();
            jdbc.sql("INSERT INTO integration.fraud_result(attempt_id,inference_id,result,created_at) VALUES(:a,:id,CAST(:result AS jsonb),:now) ON CONFLICT DO NOTHING")
                .param("a",attemptId).param("id",id).param("result",json.writeValueAsString(result)).param("now",Timestamp.from(clock.instant())).update();
            return Optional.of(new Result(id,n.doubleValue()));
        }catch(RuntimeException e){
            org.slf4j.LoggerFactory.getLogger(getClass()).warn("Synthetic proxy unavailable attemptId={} error={}",attemptId,e.getClass().getSimpleName());
            return Optional.empty();
        }
    }
}
