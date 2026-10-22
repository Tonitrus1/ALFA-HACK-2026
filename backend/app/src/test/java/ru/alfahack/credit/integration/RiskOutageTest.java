package ru.alfahack.credit.integration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.Primary;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.web.servlet.MockMvc;

import ru.alfahack.credit.integration.application.ReviewWorker;
import ru.alfahack.credit.journey.application.OutboxDispatcher;
import ru.alfahack.credit.ml.application.MlClient;
import ru.alfahack.credit.ml.application.MlContracts;
import ru.alfahack.credit.support.DemoClient;
import ru.alfahack.credit.support.Financials;
import ru.alfahack.credit.support.IntegrationTest;
import ru.alfahack.credit.support.Journey;

/** A18: модель риска недоступна → MANUAL, без автоматического отказа и без записи инференса. */
@IntegrationTest
@Import(RiskOutageTest.FailingMl.class)
class RiskOutageTest {

    @TestConfiguration(proxyBeanMethods = false)
    static class FailingMl {

        @Bean
        @Primary
        MlClient failingMlClient() {
            return new MlClient() {
                @Override
                public String mode() {
                    return "MODEL";
                }

                @Override
                public MlContracts.FeatureSnapshot createFeatureSnapshot(String key, MlContracts.FeatureSnapshotInput in) {
                    throw new IllegalStateException("ML timeout");
                }

                @Override
                public MlContracts.RiskResult evaluateRisk(String key, MlContracts.RiskRequest request) {
                    throw new IllegalStateException("ML timeout");
                }

                @Override
                public MlContracts.RankingResult rank(String key, MlContracts.RankingRequest request) {
                    throw new IllegalStateException("ML timeout");
                }

                @Override
                public MlContracts.AssistantResponse answer(MlContracts.RagInput input) {
                    throw new IllegalStateException("ML timeout");
                }
            };
        }
    }

    @Autowired
    MockMvc mvc;

    @Autowired
    JdbcClient jdbc;

    @Autowired
    OutboxDispatcher dispatcher;

    @Autowired
    ReviewWorker reviews;

    @Test
    void riskOutageGoesToManual() throws Exception {
        DemoClient a = DemoClient.login(mvc, "representative-a");
        Journey journey = new Journey(mvc, a, dispatcher, reviews);
        journey.settle();
        String id = journey.submit(50_000_000, "{\"businessAgeMonths\":40}", Financials.values(100_000_000,
                40_000_000, 50_000_000, 20_000_000, 60_000_000, 300_000_000, 10_000_000, 15_000_000));
        journey.settle();

        mvc.perform(a.sign(get("/api/v1/applications/" + id + "/status")))
                .andExpect(jsonPath("$.status").value("MANUAL"))
                .andExpect(jsonPath("$.nextAction.type").value("WAIT"));
        mvc.perform(a.sign(get("/api/v1/applications/" + id + "/decision")))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("DECISION_NOT_READY"));
        String reasons = jdbc.sql("SELECT array_to_string(reason_codes, ',') || '|' || risk_mode "
                        + "FROM integration.decision WHERE application_id = :id")
                .param("id", id).query(String.class).single();
        assertThat(reasons).isEqualTo("RISK_UNAVAILABLE|UNAVAILABLE");
        long inferences = jdbc.sql("SELECT count(*) FROM ml.inference_record WHERE application_id = :id")
                .param("id", id).query(Long.class).single();
        assertThat(inferences).isZero();
    }
}
