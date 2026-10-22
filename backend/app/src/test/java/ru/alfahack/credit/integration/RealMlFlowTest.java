package ru.alfahack.credit.integration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
import java.nio.file.*;
import java.util.*;
import com.jayway.jsonpath.JsonPath;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.condition.EnabledIfSystemProperty;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import tools.jackson.databind.json.JsonMapper;
import ru.alfahack.credit.support.*;
import ru.alfahack.credit.integration.application.ReviewWorker;
import ru.alfahack.credit.journey.application.OutboxDispatcher;

/** Opt-in acceptance: actual Java HTTP client -> bridge -> actual CatBoost / E5 / PostgreSQL. */
@IntegrationTest
@EnabledIfSystemProperty(named="integration.realMl",matches="true")
class RealMlFlowTest {
    @DynamicPropertySource static void properties(DynamicPropertyRegistry r) throws Exception {
        Map<?,?> cfg=JsonMapper.builder().build().readValue(Files.readString(Path.of(System.getProperty("integration.config"))),Map.class);
        r.add("credit.ml.mode",()->"http");r.add("credit.ml.base-url",()->"http://127.0.0.1:18000");r.add("credit.ml.service-token",()->cfg.get("token"));
    }
    @Autowired MockMvc mvc;
    @Autowired JdbcClient jdbc;
    @Autowired OutboxDispatcher dispatcher;
    @Autowired ReviewWorker reviews;
    DemoClient a;
    Journey journey;
    static final String HEALTHY=Financials.values(100000000,40000000,50000000,20000000,60000000,300000000,10000000,15000000);
    @BeforeEach void start() throws Exception { a=DemoClient.login(mvc,"representative-a");journey=new Journey(mvc,a,dispatcher,reviews);journey.settle(); }
    @Test void realRiskIsRecordedAndRepeatedReviewKeepsOneInference() throws Exception {
        String id=journey.submit(50000000,"{\"businessAgeMonths\":40}",HEALTHY);journey.settle();
        mvc.perform(a.sign(get("/api/v1/applications/"+id+"/decision"))).andExpect(status().isOk()).andExpect(jsonPath("$.outcome").value("APPROVED"));
        assertThat(jdbc.sql("SELECT mode FROM ml.inference_record WHERE application_id=:id").param("id",id).query(String.class).single()).isEqualTo("MODEL");
        journey.settle();
        assertThat(jdbc.sql("SELECT count(*) FROM ml.inference_record WHERE application_id=:id").param("id",id).query(Long.class).single()).isEqualTo(1);
    }
    @Test void backendBalanceToleranceUsesRealModelWithoutRepair() throws Exception {
        String id=journey.submit(50000000,"{\"businessAgeMonths\":40}",HEALTHY.replace("60000000","60500000"));journey.settle();
        assertThat(jdbc.sql("SELECT mode FROM ml.inference_record WHERE application_id=:id").param("id",id).query(String.class).single()).isEqualTo("MODEL");
    }
    @Test void realFeedReturnsModelAndPublicContract() throws Exception {
        mvc.perform(a.json(put("/api/v1/feed/preferences").param("companyId","company-a"),"{\"task\":\"EQUIPMENT\",\"help\":\"COST\",\"depth\":\"PRACTICAL\"}"))
            .andExpect(status().isOk());
        String response=mvc.perform(a.sign(get("/api/v1/feed").param("companyId","company-a")))
            .andExpect(status().isOk()).andExpect(jsonPath("$.rankingMode").value("MODEL")).andExpect(jsonPath("$.cards.length()").value(6))
            .andReturn().getResponse().getContentAsString();
        assertThat(response).doesNotContain("score","internalReasonCodes","Service-Token");
        String card=JsonPath.read(response,"$.cards[0].illustration");
        mvc.perform(get(card)).andExpect(status().isOk()).andExpect(content().contentTypeCompatibleWith("image/svg+xml"));
    }
    String caseStatus(String id) throws Exception {
        return JsonPath.read(mvc.perform(a.sign(get("/api/v1/applications/"+id+"/status")))
            .andReturn().getResponse().getContentAsString(),"$.status");
    }

    @Test
    void realFinanceOnlyRfiRoundTrip() throws Exception {
        String id = journey.submit(50_000_000, "{\"businessAgeMonths\":40,\"annualRevenue\":"
                + "{\"amountMinor\":1000000000,\"currency\":\"RUB\"}}", HEALTHY);
        journey.settle();
        assertThat(caseStatus(id)).isEqualTo("NEEDS_INFO");
        String originalSnapshot = JsonPath.read(mvc.perform(a.sign(get("/api/v1/applications/" + id)))
                .andReturn().getResponse().getContentAsString(), "$.financialSnapshotId");

        String list = mvc.perform(a.sign(get("/api/v1/applications/" + id + "/information-requests")))
                .andExpect(jsonPath("$.items[0].status").value("OPEN"))
                .andExpect(jsonPath("$.items[0].items[0].kind").value("FIELD"))
                .andExpect(jsonPath("$.items[0].items[0].fieldPath").value("financialStatement.values.revenueMinor"))
                .andReturn().getResponse().getContentAsString();
        String requestId = JsonPath.read(list, "$.items[0].requestId");
        String base = "/api/v1/applications/" + id + "/information-requests/" + requestId;

        mvc.perform(a.sign(get(base + "/draft")))
                .andExpect(jsonPath("$.draftVersion").value(1))
                .andExpect(jsonPath("$.financialStatementVersion").value(1));
        mvc.perform(a.sign(get(base + "/draft/financial-statement")))
                .andExpect(jsonPath("$.confirmed").value(true))
                .andExpect(jsonPath("$.statement.values.revenueMinor").value(300_000_000));

        // Незапрошенное поле (чистая прибыль) менять нельзя.
        mvc.perform(a.json(put(base + "/draft/financial-statement"),
                        Financials.input(HEALTHY.replace("\"netProfitMinor\":10000000", "\"netProfitMinor\":11000000")))
                        .header("If-Match", "\"v1\"").header("Idempotency-Key", UUID.randomUUID().toString()))
                .andExpect(status().isUnprocessableContent())
                .andExpect(jsonPath("$.code").value("FIELD_NOT_REQUESTED"));

        mvc.perform(a.json(put(base + "/draft/financial-statement"),
                        Financials.input(HEALTHY.replace("300000000", "310000000")))
                        .header("If-Match", "\"v1\"").header("Idempotency-Key", UUID.randomUUID().toString()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.statementVersion").value(2))
                .andExpect(jsonPath("$.confirmed").value(false));
        mvc.perform(a.json(post(base + "/draft/financial-statement/confirm"), Financials.confirmation(2))
                        .header("If-Match", "\"v2\"").header("Idempotency-Key", UUID.randomUUID().toString()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.confirmed").value(true));

        String response = """
                {"requestVersion":1,"documentIds":[],"documentReferences":[],"requirementsVersion":1,
                 "draftVersion":%d,"financialStatementVersion":2}
                """;
        mvc.perform(a.json(post(base + "/responses"), response.formatted(1))
                        .header("Idempotency-Key", "respond-" + UUID.randomUUID()))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("INFORMATION_DRAFT_CONFLICT"));
        String receipt = mvc.perform(a.json(post(base + "/responses"), response.formatted(3))
                        .header("Idempotency-Key", "respond-" + UUID.randomUUID()))
                .andExpect(status().isAccepted())
                .andReturn().getResponse().getContentAsString();

        journey.settle();

        mvc.perform(a.sign(get("/api/v1/operations/" + JsonPath.read(receipt, "$.operationId"))))
                .andExpect(jsonPath("$.operationType").value("RESPOND"))
                .andExpect(jsonPath("$.status").value("SUCCEEDED"))
                .andExpect(jsonPath("$.resourceId").value(requestId));
        mvc.perform(a.sign(get("/api/v1/applications/" + id + "/information-requests")))
                .andExpect(jsonPath("$.items[0].status").value("CLOSED"));
        assertThat(caseStatus(id)).isEqualTo("APPROVED");

        // Исходная анкета и её снимок неизменны; решение принято по новому снимку ответа.
        mvc.perform(a.sign(get("/api/v1/applications/" + id)))
                .andExpect(jsonPath("$.status").value("SUBMITTED"))
                .andExpect(jsonPath("$.financialSnapshotId").value(originalSnapshot))
                .andExpect(jsonPath("$.financialStatementVersion").value(1));
        String originalRevenue = jdbc.sql("SELECT statement->'values'->>'revenueMinor' FROM applications.financial_snapshot "
                + "WHERE financial_snapshot_id = :id").param("id", originalSnapshot).query(String.class).single();
        assertThat(originalRevenue).isEqualTo("300000000");
        String decisionSnapshotRevenue = jdbc.sql("""
                        SELECT s.statement->'values'->>'revenueMinor' FROM integration.decision d
                        JOIN applications.financial_snapshot s ON s.financial_snapshot_id = d.financial_snapshot_id
                        WHERE d.application_id = :id ORDER BY d.case_version DESC LIMIT 1
                        """).param("id", id).query(String.class).single();
        assertThat(decisionSnapshotRevenue).isEqualTo("310000000");
    }
}
