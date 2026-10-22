package ru.alfahack.credit.applications;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

import com.jayway.jsonpath.JsonPath;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Import;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import ru.alfahack.credit.journey.application.OutboxDispatcher;
import ru.alfahack.credit.support.Bodies;
import ru.alfahack.credit.support.ConfirmedFinancials;
import ru.alfahack.credit.support.DemoClient;
import ru.alfahack.credit.support.IntegrationTest;

/** P05 «submit receipt dedup» и событие симулятора: SUBMITTED → REVIEW через outbox. */
@IntegrationTest
@Import(ConfirmedFinancials.class)
class SubmitFlowTest {

    @Autowired
    MockMvc mvc;

    @Autowired
    JdbcClient jdbc;

    @Autowired
    OutboxDispatcher dispatcher;

    DemoClient a;

    @BeforeEach
    void login() throws Exception {
        a = DemoClient.login(mvc, "representative-a");
    }

    String createDraft(long amountMinor) throws Exception {
        String body = mvc.perform(a.json(post("/api/v1/applications"), Bodies.create("company-a", amountMinor, 12))
                        .header("Idempotency-Key", "create-" + UUID.randomUUID()))
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString();
        return JsonPath.read(body, "$.applicationId");
    }

    MvcResult submit(String applicationId, String key, String body) throws Exception {
        return mvc.perform(a.json(post("/api/v1/applications/" + applicationId + "/submit"), body)
                        .header("Idempotency-Key", key))
                .andReturn();
    }

    @Test
    void submitReturnsReceiptAndRepeatReturnsSameReceipt() throws Exception {
        String id = createDraft(50_000_000);
        String key = "submit-" + UUID.randomUUID();

        MvcResult first = submit(id, key, Bodies.submit(1, 1));
        assertThat(first.getResponse().getStatus()).isEqualTo(202);
        String operationId = JsonPath.read(first.getResponse().getContentAsString(), "$.operationId");
        assertThat(first.getResponse().getHeader("Location")).isEqualTo("/api/v1/operations/" + operationId);
        assertThat(first.getResponse().getHeader("Retry-After")).isEqualTo("1");

        MvcResult repeat = submit(id, key, Bodies.submit(1, 1));
        assertThat(repeat.getResponse().getStatus()).isEqualTo(202);
        assertThat(repeat.getResponse().getContentAsString()).isEqualTo(first.getResponse().getContentAsString());

        MvcResult otherBody = submit(id, key, Bodies.submit(2, 1));
        assertThat(otherBody.getResponse().getStatus()).isEqualTo(409);
        assertThat((String) JsonPath.read(otherBody.getResponse().getContentAsString(), "$.code"))
                .isEqualTo("IDEMPOTENCY_KEY_REUSED");

        MvcResult otherKey = submit(id, "submit-" + UUID.randomUUID(), Bodies.submit(1, 1));
        assertThat(otherKey.getResponse().getStatus()).isEqualTo(409);
        assertThat((String) JsonPath.read(otherKey.getResponse().getContentAsString(), "$.code"))
                .isEqualTo("APPLICATION_ALREADY_SUBMITTED");

        assertThat(count("journey.command_operation WHERE application_id = '" + id + "'")).isEqualTo(1);
        assertThat(count("journey.outbox WHERE application_id = '" + id + "'")).isEqualTo(1);
        assertThat(count("applications.submission_snapshot WHERE application_id = '" + id + "'")).isEqualTo(1);
    }

    @Test
    void concurrentSubmitsWithSameKeyShareOneOperation() throws Exception {
        String id = createDraft(50_000_000);
        String key = "submit-" + UUID.randomUUID();
        ExecutorService pool = Executors.newFixedThreadPool(4);
        try {
            List<Future<MvcResult>> futures = new ArrayList<>();
            for (int i = 0; i < 4; i++) {
                Callable<MvcResult> call = () -> submit(id, key, Bodies.submit(1, 1));
                futures.add(pool.submit(call));
            }
            Set<String> operationIds = new HashSet<>();
            for (Future<MvcResult> future : futures) {
                MvcResult result = future.get();
                assertThat(result.getResponse().getStatus()).isEqualTo(202);
                operationIds.add(JsonPath.read(result.getResponse().getContentAsString(), "$.operationId"));
            }
            assertThat(operationIds).hasSize(1);
        } finally {
            pool.shutdownNow();
        }
        assertThat(count("journey.outbox WHERE application_id = '" + id + "'")).isEqualTo(1);
    }

    @Test
    void simulatorAcceptsCaseOnceAndOperationSucceeds() throws Exception {
        String id = createDraft(50_000_000);
        String body = submit(id, "submit-" + UUID.randomUUID(), Bodies.submit(1, 1)).getResponse().getContentAsString();
        String operationId = JsonPath.read(body, "$.operationId");

        mvc.perform(a.sign(get("/api/v1/operations/" + operationId)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("PENDING"))
                .andExpect(jsonPath("$.operationType").value("SUBMIT"))
                .andExpect(jsonPath("$.resourceId").value(id));
        mvc.perform(a.sign(get("/api/v1/applications/" + id + "/status")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("SUBMITTED"))
                .andExpect(jsonPath("$.nextAction.type").value("WAIT"));

        dispatchAll();

        mvc.perform(a.sign(get("/api/v1/operations/" + operationId)))
                .andExpect(jsonPath("$.status").value("SUCCEEDED"))
                .andExpect(jsonPath("$.resultCode").value("CASE_ACCEPTED"));
        mvc.perform(a.sign(get("/api/v1/applications/" + id + "/status")))
                .andExpect(status().isOk())
                .andExpect(header().exists("ETag"))
                .andExpect(jsonPath("$.status").value("REVIEW"))
                .andExpect(jsonPath("$.caseVersion").value(1))
                .andExpect(jsonPath("$.sourceVersion").value(1))
                .andExpect(jsonPath("$.history.length()").value(3));

        // Повторная доставка того же события (потерянный ack) не создаёт второе дело.
        jdbc.sql("UPDATE journey.outbox SET state = 'PENDING', delivered_at = NULL WHERE application_id = :id "
                        + "AND event_type = 'SubmissionRequested'")
                .param("id", id).update();
        dispatchAll();
        assertThat(count("integration.bank_case WHERE application_id = '" + id + "'")).isEqualTo(1);
    }

    @Test
    void submittedApplicationIsImmutable() throws Exception {
        String id = createDraft(50_000_000);
        submit(id, "submit-" + UUID.randomUUID(), Bodies.submit(1, 1));

        mvc.perform(a.json(patch("/api/v1/applications/" + id), "{\"termMonths\":6}").header("If-Match", "\"v2\""))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("APPLICATION_NOT_EDITABLE"));
        assertThatThrownBy(() -> jdbc.sql(
                        "UPDATE applications.submission_snapshot SET package_digest = 'x' WHERE application_id = :id")
                .param("id", id).update())
                .hasMessageContaining("immutable");
    }

    @Test
    void submitChecksVersionsAndProductLimits() throws Exception {
        String id = createDraft(50_000_000);
        assertThat(submit(id, "submit-" + UUID.randomUUID(), Bodies.submit(7, 1)).getResponse().getStatus())
                .isEqualTo(409);
        assertThat(submit(id, "submit-" + UUID.randomUUID(), Bodies.submit(1, 2)).getResponse().getContentAsString())
                .contains("FINANCIAL_CONFIRMATION_REQUIRED");
        assertThat(submit(id, "submit-" + UUID.randomUUID(), """
                {"expectedVersion":1,"consentRecordIds":[],"documentIds":["d1"],"documentReferences":[],
                 "requirementsVersion":1,"financialStatementVersion":1}
                """).getResponse().getContentAsString()).contains("DOCUMENT_REFERENCES_MISMATCH");
        assertThat(submit(id, "submit-" + UUID.randomUUID(), """
                {"expectedVersion":1,"consentRecordIds":[],"documentIds":[],"documentReferences":[],
                 "requirementsVersion":2,"financialStatementVersion":1}
                """).getResponse().getContentAsString()).contains("DOCUMENT_REQUIREMENTS_CHANGED");

        String tooBig = createDraft(900_000_000);
        assertThat(submit(tooBig, "submit-" + UUID.randomUUID(), Bodies.submit(1, 1)).getResponse().getContentAsString())
                .contains("TERMS_OUT_OF_RANGE");
    }

    @Test
    void operationIsVisibleOnlyToItsActorAndCompany() throws Exception {
        String id = createDraft(50_000_000);
        String body = submit(id, "submit-" + UUID.randomUUID(), Bodies.submit(1, 1)).getResponse().getContentAsString();
        String operationId = JsonPath.read(body, "$.operationId");
        DemoClient b = DemoClient.login(mvc, "representative-b");

        mvc.perform(b.sign(get("/api/v1/operations/" + operationId))).andExpect(status().isNotFound());
    }

    private void dispatchAll() {
        while (dispatcher.dispatchOnce() > 0) {
            // доставляем, пока есть готовые события (в т.ч. порождённые обработчиками)
        }
    }

    private long count(String fromWhere) {
        return jdbc.sql("SELECT count(*) FROM " + fromWhere).query(Long.class).single();
    }
}
