package ru.alfahack.credit.integration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.UUID;

import com.jayway.jsonpath.JsonPath;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.web.servlet.MockMvc;

import ru.alfahack.credit.integration.application.ReviewWorker;
import ru.alfahack.credit.journey.application.OutboxDispatcher;
import ru.alfahack.credit.support.DemoClient;
import ru.alfahack.credit.support.Financials;
import ru.alfahack.credit.support.IntegrationTest;
import ru.alfahack.credit.support.Journey;

/** Симулятор по demo-policy v1 с контрактным двойником ML: A03, A04, предложение и финансовый RFI (A02). */
@IntegrationTest
class DecisionFlowTest {

    static final String BUSINESS = "{\"businessAgeMonths\":40}";
    static final String HEALTHY = Financials.values(100_000_000, 40_000_000, 50_000_000, 20_000_000, 60_000_000,
            300_000_000, 10_000_000, 15_000_000);

    @Autowired
    MockMvc mvc;

    @Autowired
    JdbcClient jdbc;

    @Autowired
    OutboxDispatcher dispatcher;

    @Autowired
    ReviewWorker reviews;

    DemoClient a;
    Journey journey;

    @BeforeEach
    void setUp() throws Exception {
        a = DemoClient.login(mvc, "representative-a");
        journey = new Journey(mvc, a, dispatcher, reviews);
        journey.settle();
    }

    String caseStatus(String id) throws Exception {
        return JsonPath.read(mvc.perform(a.sign(get("/api/v1/applications/" + id + "/status")))
                .andExpect(status().isOk()).andReturn().getResponse().getContentAsString(), "$.status");
    }

    @Test
    void approvedWithAvailableOffer() throws Exception {
        String id = journey.submit(50_000_000, BUSINESS, HEALTHY);
        journey.settle();

        assertThat(caseStatus(id)).isEqualTo("APPROVED");
        String decision = mvc.perform(a.sign(get("/api/v1/applications/" + id + "/decision")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.outcome").value("APPROVED"))
                .andExpect(jsonPath("$.caseVersion").value(2))
                .andReturn().getResponse().getContentAsString();
        String offerId = JsonPath.read(decision, "$.offerIds[0]");
        mvc.perform(a.sign(get("/api/v1/offers/" + offerId)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("AVAILABLE"))
                .andExpect(jsonPath("$.amount.amountMinor").value(50_000_000))
                .andExpect(jsonPath("$.termMonths").value(12))
                .andExpect(jsonPath("$.validUntil").isNotEmpty());
        mvc.perform(a.sign(get("/api/v1/applications/" + id + "/status")))
                .andExpect(jsonPath("$.nextAction.type").value("VIEW_OFFER"));

        String riskMode = jdbc.sql("SELECT risk_mode FROM integration.decision WHERE application_id = :id")
                .param("id", id).query(String.class).single();
        assertThat(riskMode).isEqualTo("CONTRACT_DOUBLE");
        DemoClient b = DemoClient.login(mvc, "representative-b");
        mvc.perform(b.sign(get("/api/v1/offers/" + offerId))).andExpect(status().isNotFound());
        mvc.perform(b.sign(get("/api/v1/applications/" + id + "/decision"))).andExpect(status().isNotFound());
    }

    @Test
    void declinedOnDebtRatioWithoutOffer() throws Exception {
        String id = journey.submit(50_000_000, BUSINESS, Financials.values(100_000_000, 92_000_000, 50_000_000,
                30_000_000, 8_000_000, 300_000_000, 1_000_000, 2_000_000));
        journey.settle();

        assertThat(caseStatus(id)).isEqualTo("DECLINED");
        mvc.perform(a.sign(get("/api/v1/applications/" + id + "/decision")))
                .andExpect(jsonPath("$.outcome").value("DECLINED"))
                .andExpect(jsonPath("$.offerIds.length()").value(0))
                .andExpect(jsonPath("$.publicExplanation").value("Долговая нагрузка выше допустимой для продукта"));
    }

    @Test
    void alternativeAboveTurnoverCapKeepsApplicationUnchanged() throws Exception {
        String id = journey.submit(50_000_000, BUSINESS, Financials.values(100_000_000, 40_000_000, 50_000_000,
                20_000_000, 60_000_000, 100_000_000, 10_000_000, 15_000_000));
        journey.settle();

        assertThat(caseStatus(id)).isEqualTo("ALTERNATIVE");
        String decision = mvc.perform(a.sign(get("/api/v1/applications/" + id + "/decision")))
                .andReturn().getResponse().getContentAsString();
        mvc.perform(a.sign(get("/api/v1/offers/" + JsonPath.read(decision, "$.offerIds[0]"))))
                .andExpect(jsonPath("$.amount.amountMinor").value(25_000_000));
        mvc.perform(a.sign(get("/api/v1/applications/" + id)))
                .andExpect(jsonPath("$.terms.amount.amountMinor").value(50_000_000));
    }

    @Test
    void financeOnlyRfiRoundTrip() throws Exception {
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
