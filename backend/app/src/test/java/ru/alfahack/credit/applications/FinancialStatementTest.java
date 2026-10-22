package ru.alfahack.credit.applications;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.UUID;

import com.jayway.jsonpath.JsonPath;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;

import ru.alfahack.credit.support.Bodies;
import ru.alfahack.credit.support.DemoClient;
import ru.alfahack.credit.support.Financials;
import ru.alfahack.credit.support.IntegrationTest;

/** P08 «all 8; CAS; modified values invalidate confirmation» и неизменяемый финансовый снимок пакета. */
@IntegrationTest
class FinancialStatementTest {

    static final String INCOMPLETE = "{\"totalAssetsMinor\":100000000,\"revenueMinor\":0}";

    @Autowired
    MockMvc mvc;

    @Autowired
    JdbcClient jdbc;

    DemoClient a;
    String id;
    String path;

    @BeforeEach
    void draft() throws Exception {
        a = DemoClient.login(mvc, "representative-a");
        String body = mvc.perform(a.json(post("/api/v1/applications"), Bodies.create("company-a", 50_000_000, 12))
                        .header("Idempotency-Key", "create-" + UUID.randomUUID()))
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString();
        id = JsonPath.read(body, "$.applicationId");
        path = "/api/v1/applications/" + id + "/financial-statement";
    }

    ResultActions save(long ifMatch, String inputJson) throws Exception {
        return save(ifMatch, inputJson, UUID.randomUUID().toString());
    }

    ResultActions save(long ifMatch, String inputJson, String key) throws Exception {
        return mvc.perform(a.json(put(path), inputJson)
                .header("If-Match", "\"v" + ifMatch + "\"")
                .header("Idempotency-Key", key));
    }

    ResultActions confirm(long ifMatch, String confirmationJson) throws Exception {
        return mvc.perform(a.json(post(path + "/confirm"), confirmationJson)
                .header("If-Match", "\"v" + ifMatch + "\"")
                .header("Idempotency-Key", UUID.randomUUID().toString()));
    }

    @Test
    void incompleteDraftIsSavedButCannotBeConfirmed() throws Exception {
        mvc.perform(a.sign(get(path))).andExpect(status().isNotFound());

        save(1, Financials.input(INCOMPLETE))
                .andExpect(status().isOk())
                .andExpect(header().string("ETag", "\"v2\""))
                .andExpect(jsonPath("$.statementVersion").value(1))
                .andExpect(jsonPath("$.containerVersion").value(2))
                .andExpect(jsonPath("$.confirmed").value(false))
                .andExpect(jsonPath("$.statement.values.revenueMinor").value(0))
                .andExpect(jsonPath("$.statement.values.equityMinor").doesNotExist());

        confirm(2, Financials.confirmation(1))
                .andExpect(status().isUnprocessableContent())
                .andExpect(jsonPath("$.code").value("FINANCIAL_VALUES_INCOMPLETE"));
    }

    @Test
    void confirmationRecordsServerProvenanceForAllEight() throws Exception {
        save(1, Financials.input(Financials.COMPLETE_VALUES)).andExpect(status().isOk());

        confirm(2, Financials.confirmation(1))
                .andExpect(status().isOk())
                .andExpect(header().string("ETag", "\"v3\""))
                .andExpect(jsonPath("$.confirmed").value(true))
                .andExpect(jsonPath("$.statementVersion").value(1))
                .andExpect(jsonPath("$.provenance.length()").value(8))
                .andExpect(jsonPath("$.provenance[0].sourceType").value("MANUAL"))
                .andExpect(jsonPath("$.provenance[0].confirmedBy").value("representative-a"));
    }

    @Test
    void modifiedValuesInvalidateConfirmation() throws Exception {
        save(1, Financials.input(Financials.COMPLETE_VALUES));
        confirm(2, Financials.confirmation(1)).andExpect(status().isOk());

        // Тот же ввод — не изменение: подтверждение и версии сохраняются.
        save(3, Financials.input(Financials.COMPLETE_VALUES))
                .andExpect(jsonPath("$.confirmed").value(true))
                .andExpect(jsonPath("$.containerVersion").value(3));

        save(3, Financials.input(Financials.COMPLETE_VALUES.replace("250000000", "260000000")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.statementVersion").value(2))
                .andExpect(jsonPath("$.confirmed").value(false))
                .andExpect(jsonPath("$.provenance.length()").value(0));
    }

    @Test
    void casRejectsStaleVersions() throws Exception {
        save(1, Financials.input(Financials.COMPLETE_VALUES)).andExpect(status().isOk());

        save(1, Financials.input(INCOMPLETE))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("DRAFT_VERSION_CONFLICT"));
        save(2, Financials.input(INCOMPLETE)).andExpect(status().isOk());
        confirm(3, Financials.confirmation(1))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("FINANCIAL_STATEMENT_VERSION_CONFLICT"));
    }

    @Test
    void invariantsAreChecked() throws Exception {
        save(1, Financials.input(Financials.COMPLETE_VALUES.replace("\"currentAssetsMinor\":50000000",
                "\"currentAssetsMinor\":150000000")));
        confirm(2, Financials.confirmation(1))
                .andExpect(status().isUnprocessableContent())
                .andExpect(jsonPath("$.code").value("FINANCIAL_INVARIANT_VIOLATED"));

        // Расхождение баланса 2% > допуска 1%.
        save(2, Financials.input(Financials.COMPLETE_VALUES.replace("\"equityMinor\":40000000",
                "\"equityMinor\":38000000")));
        confirm(3, Financials.confirmation(2))
                .andExpect(status().isUnprocessableContent())
                .andExpect(jsonPath("$.code").value("FINANCIAL_INVARIANT_VIOLATED"));

        // Расхождение 0,5% в пределах demo-допуска.
        save(3, Financials.input(Financials.COMPLETE_VALUES.replace("\"equityMinor\":40000000",
                "\"equityMinor\":39500000")));
        confirm(4, Financials.confirmation(3)).andExpect(status().isOk());
    }

    @Test
    void periodMustBeOneCalendarYear() throws Exception {
        save(1, Financials.input(Financials.COMPLETE_VALUES).replace("2025-12-31", "2025-06-30"))
                .andExpect(status().isUnprocessableContent())
                .andExpect(jsonPath("$.code").value("FINANCIAL_PERIOD_INVALID"));
    }

    @Test
    void clientCannotSendConfirmationOrProvenance() throws Exception {
        save(1, Financials.input(Financials.COMPLETE_VALUES).replace("\"currency\":\"RUB\"",
                "\"currency\":\"RUB\",\"confirmed\":true"))
                .andExpect(status().isBadRequest());
        confirm(1, Financials.confirmation(1).replace("\"ebitMinor\"", "\"ebitMinor\",\"ebitMinor\""))
                .andExpect(status().isBadRequest());
    }

    @Test
    void saveIsIdempotentByKey() throws Exception {
        String key = UUID.randomUUID().toString();
        save(1, Financials.input(INCOMPLETE), key).andExpect(jsonPath("$.containerVersion").value(2));
        save(1, Financials.input(INCOMPLETE), key)
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.containerVersion").value(2))
                .andExpect(jsonPath("$.statementVersion").value(1));
        save(1, Financials.input(Financials.COMPLETE_VALUES), key)
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("IDEMPOTENCY_KEY_REUSED"));
    }

    @Test
    void otherCompanyCannotReadOrWrite() throws Exception {
        save(1, Financials.input(INCOMPLETE)).andExpect(status().isOk());
        DemoClient b = DemoClient.login(mvc, "representative-b");

        mvc.perform(b.sign(get(path))).andExpect(status().isNotFound());
        mvc.perform(b.json(put(path), Financials.input(INCOMPLETE))
                        .header("If-Match", "\"v2\"").header("Idempotency-Key", UUID.randomUUID().toString()))
                .andExpect(status().isNotFound());
    }

    @Test
    void submitPinsImmutableFinancialSnapshot() throws Exception {
        long version = Financials.fillAndConfirm(mvc, a, id, 1);

        mvc.perform(a.json(post("/api/v1/applications/" + id + "/submit"), Bodies.submit(version, 1))
                        .header("Idempotency-Key", "submit-" + UUID.randomUUID()))
                .andExpect(status().isAccepted());

        String snapshotId = mvc.perform(a.sign(get("/api/v1/applications/" + id)))
                .andExpect(jsonPath("$.status").value("SUBMITTED"))
                .andExpect(jsonPath("$.financialStatementVersion").value(1))
                .andReturn().getResponse().getContentAsString();
        snapshotId = JsonPath.read(snapshotId, "$.financialSnapshotId");
        String revenue = jdbc.sql("SELECT statement->'values'->>'revenueMinor' FROM applications.financial_snapshot "
                        + "WHERE financial_snapshot_id = :id")
                .param("id", snapshotId).query(String.class).single();
        assertThat(revenue).isEqualTo("250000000");

        final String snapshot = snapshotId;
        assertThatThrownBy(() -> jdbc.sql("UPDATE applications.financial_snapshot SET statement_digest = 'x' "
                        + "WHERE financial_snapshot_id = :id").param("id", snapshot).update())
                .hasMessageContaining("immutable");
        save(version + 1, Financials.input(INCOMPLETE))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("APPLICATION_NOT_EDITABLE"));
    }

    @Test
    void submitRejectsUnconfirmedOrStaleStatementVersion() throws Exception {
        save(1, Financials.input(Financials.COMPLETE_VALUES));
        mvc.perform(a.json(post("/api/v1/applications/" + id + "/submit"), Bodies.submit(2, 1))
                        .header("Idempotency-Key", "submit-" + UUID.randomUUID()))
                .andExpect(status().isUnprocessableContent())
                .andExpect(jsonPath("$.code").value("FINANCIAL_CONFIRMATION_REQUIRED"));

        confirm(2, Financials.confirmation(1)).andExpect(status().isOk());
        save(3, Financials.input(Financials.COMPLETE_VALUES.replace("250000000", "260000000")));
        // Подтверждена была версия 1, сейчас неподтверждённая версия 2.
        mvc.perform(a.json(post("/api/v1/applications/" + id + "/submit"), Bodies.submit(4, 1))
                        .header("Idempotency-Key", "submit-" + UUID.randomUUID()))
                .andExpect(status().isUnprocessableContent())
                .andExpect(jsonPath("$.code").value("FINANCIAL_CONFIRMATION_REQUIRED"));
    }
}
