package ru.alfahack.credit.support;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.UUID;

import com.jayway.jsonpath.JsonPath;

import org.springframework.test.web.servlet.MockMvc;

/** Заполнение и подтверждение финансовой анкеты через публичный API. */
public final class Financials {

    /** Согласованный набор: 1 000 000 = 600 000 + 400 000 (копейки). */
    public static final String COMPLETE_VALUES = """
            {"totalAssetsMinor":100000000,"totalLiabilitiesMinor":60000000,"currentAssetsMinor":50000000,
             "currentLiabilitiesMinor":30000000,"equityMinor":40000000,"revenueMinor":250000000,
             "netProfitMinor":-1500000,"ebitMinor":2000000}
            """;

    public static final String ALL_FIELDS = """
            ["totalAssetsMinor","totalLiabilitiesMinor","currentAssetsMinor","currentLiabilitiesMinor",
             "equityMinor","revenueMinor","netProfitMinor","ebitMinor"]
            """;

    private Financials() {
    }

    public static String input(String valuesJson) {
        return """
                {"periodStart":"2025-01-01","periodEnd":"2025-12-31","reportingStandard":"DEMO","currency":"RUB",
                 "values":%s,"sourceDocumentReferences":[]}
                """.formatted(valuesJson);
    }

    public static String confirmation(long expectedStatementVersion) {
        return """
                {"expectedStatementVersion":%d,"confirmedFieldNames":%s,"documentReferences":[]}
                """.formatted(expectedStatementVersion, ALL_FIELDS);
    }

    /** Сохраняет полную форму и подтверждает её; возвращает новую версию заявки (ETag). */
    public static long fillAndConfirm(MockMvc mvc, DemoClient client, String applicationId, long applicationVersion)
            throws Exception {
        String path = "/api/v1/applications/" + applicationId + "/financial-statement";
        String saved = mvc.perform(client.json(put(path), input(COMPLETE_VALUES))
                        .header("If-Match", "\"v" + applicationVersion + "\"")
                        .header("Idempotency-Key", UUID.randomUUID().toString()))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();
        long statementVersion = ((Number) JsonPath.read(saved, "$.statementVersion")).longValue();
        long containerVersion = ((Number) JsonPath.read(saved, "$.containerVersion")).longValue();
        String confirmed = mvc.perform(client.json(post(path + "/confirm"), confirmation(statementVersion))
                        .header("If-Match", "\"v" + containerVersion + "\"")
                        .header("Idempotency-Key", UUID.randomUUID().toString()))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();
        return ((Number) JsonPath.read(confirmed, "$.containerVersion")).longValue();
    }
}
