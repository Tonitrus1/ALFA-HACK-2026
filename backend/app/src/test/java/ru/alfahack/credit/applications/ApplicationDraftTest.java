package ru.alfahack.credit.applications;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
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

import ru.alfahack.credit.support.Bodies;
import ru.alfahack.credit.support.DemoClient;
import ru.alfahack.credit.support.IntegrationTest;

/** Каталог, создание, чтение и CAS-сохранение черновика; изоляция компаний; submit закрыт без финансов. */
@IntegrationTest
class ApplicationDraftTest {

    @Autowired
    MockMvc mvc;

    @Autowired
    JdbcClient jdbc;

    DemoClient a;

    @BeforeEach
    void login() throws Exception {
        a = DemoClient.login(mvc, "representative-a");
    }

    static String key() {
        return "key-" + UUID.randomUUID();
    }

    String createDraft() throws Exception {
        String body = mvc.perform(a.json(post("/api/v1/applications"), Bodies.create("company-a", 50_000_000, 12))
                        .header("Idempotency-Key", key()))
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString();
        return JsonPath.read(body, "$.applicationId");
    }

    @Test
    void catalogListsDemoProductsForSelectedCompanyOnly() throws Exception {
        mvc.perform(a.sign(get("/api/v1/products").param("companyId", "company-a")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items.length()").value(3))
                .andExpect(jsonPath("$.items[?(@.productId=='overdraft')].maxAmount.amountMinor").value(200_000_000));
        mvc.perform(a.sign(get("/api/v1/products").param("companyId", "company-b")))
                .andExpect(status().isNotFound());
    }

    @Test
    void createIsIdempotentByKey() throws Exception {
        String key = key();
        String body = Bodies.create("company-a", 50_000_000, 12);

        String first = mvc.perform(a.json(post("/api/v1/applications"), body).header("Idempotency-Key", key))
                .andExpect(status().isCreated())
                .andExpect(header().string("ETag", "\"v1\""))
                .andExpect(jsonPath("$.status").value("DRAFT"))
                .andExpect(jsonPath("$.terms.amount.amountMinor").value(50_000_000))
                .andReturn().getResponse().getContentAsString();
        String second = mvc.perform(a.json(post("/api/v1/applications"), body).header("Idempotency-Key", key))
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString();

        assertThat(second).isEqualTo(first);
        mvc.perform(a.json(post("/api/v1/applications"), Bodies.create("company-a", 60_000_000, 12))
                        .header("Idempotency-Key", key))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("IDEMPOTENCY_KEY_REUSED"));
    }

    @Test
    void createRequiresKeyAndSelectedCompany() throws Exception {
        mvc.perform(a.json(post("/api/v1/applications"), Bodies.create("company-a", 50_000_000, 12)))
                .andExpect(status().isBadRequest());
        mvc.perform(a.json(post("/api/v1/applications"), Bodies.create("company-b", 50_000_000, 12))
                        .header("Idempotency-Key", key()))
                .andExpect(status().isNotFound());
    }

    @Test
    void unknownFieldsAreRejected() throws Exception {
        mvc.perform(a.json(post("/api/v1/applications"), """
                        {"companyId":"company-a","productId":"working-capital","productVersion":1,"status":"APPROVED",
                         "need":{"purpose":"x","amount":{"amountMinor":1,"currency":"RUB"},"termMonths":3}}
                        """).header("Idempotency-Key", key()))
                .andExpect(status().isBadRequest());
    }

    @Test
    void patchUsesIfMatchAndMergesBusiness() throws Exception {
        String id = createDraft();

        mvc.perform(a.json(patch("/api/v1/applications/" + id), """
                        {"termMonths":18,"business":{"annualRevenue":{"amountMinor":900000000,"currency":"RUB"},
                         "businessAgeMonths":40}}
                        """).header("If-Match", "\"v1\""))
                .andExpect(status().isOk())
                .andExpect(header().string("ETag", "\"v2\""))
                .andExpect(jsonPath("$.terms.termMonths").value(18))
                .andExpect(jsonPath("$.terms.purpose").value("Закупка товара"))
                .andExpect(jsonPath("$.terms.business.businessAgeMonths").value(40));

        mvc.perform(a.json(patch("/api/v1/applications/" + id), "{\"termMonths\":6}").header("If-Match", "\"v1\""))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("DRAFT_VERSION_CONFLICT"));

        mvc.perform(a.json(patch("/api/v1/applications/" + id), """
                        {"business":{"businessAgeMonths":41},"clearFields":["business.businessAgeMonths"]}
                        """).header("If-Match", "\"v2\""))
                .andExpect(status().isUnprocessableContent())
                .andExpect(jsonPath("$.code").value("PATCH_FIELD_CONFLICT"));

        mvc.perform(a.json(patch("/api/v1/applications/" + id), "{\"clearFields\":[\"business.businessAgeMonths\"]}")
                        .header("If-Match", "\"v2\""))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.terms.business.businessAgeMonths").doesNotExist())
                .andExpect(jsonPath("$.terms.business.annualRevenue.amountMinor").value(900_000_000));

        mvc.perform(a.json(patch("/api/v1/applications/" + id), "{\"termMonths\":6}"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void otherCompanyCannotSeeDraft() throws Exception {
        String id = createDraft();
        DemoClient b = DemoClient.login(mvc, "representative-b");

        mvc.perform(b.sign(get("/api/v1/applications/" + id))).andExpect(status().isNotFound());
        mvc.perform(b.json(patch("/api/v1/applications/" + id), "{\"termMonths\":6}").header("If-Match", "\"v1\""))
                .andExpect(status().isNotFound());
        mvc.perform(b.json(post("/api/v1/applications/" + id + "/submit"), Bodies.submit(1, 1))
                        .header("Idempotency-Key", key()))
                .andExpect(status().isNotFound());
        mvc.perform(b.sign(get("/api/v1/applications/" + id + "/status"))).andExpect(status().isNotFound());
        mvc.perform(b.sign(get("/api/v1/applications").param("companyId", "company-a")))
                .andExpect(status().isNotFound());
    }

    @Test
    void listReturnsCompanyDraftsWithCursor() throws Exception {
        createDraft();
        createDraft();

        String page = mvc.perform(a.sign(get("/api/v1/applications")
                        .param("companyId", "company-a").param("limit", "1")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items.length()").value(1))
                .andExpect(jsonPath("$.nextCursor").isNotEmpty())
                .andReturn().getResponse().getContentAsString();
        String cursor = JsonPath.read(page, "$.nextCursor");
        String firstId = JsonPath.read(page, "$.items[0].applicationId");

        mvc.perform(a.sign(get("/api/v1/applications")
                        .param("companyId", "company-a").param("limit", "1").param("cursor", cursor)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items[0].applicationId").value(org.hamcrest.Matchers.not(firstId)));
    }

    @Test
    void submitFailsClosedWithoutConfirmedFinancials() throws Exception {
        String id = createDraft();

        mvc.perform(a.json(post("/api/v1/applications/" + id + "/submit"), Bodies.submit(1, 1))
                        .header("Idempotency-Key", key()))
                .andExpect(status().isUnprocessableContent())
                .andExpect(jsonPath("$.code").value("FINANCIAL_CONFIRMATION_REQUIRED"));

        long operations = jdbc.sql("SELECT count(*) FROM journey.command_operation WHERE application_id = :id")
                .param("id", id).query(Long.class).single();
        assertThat(operations).isZero();
        mvc.perform(a.sign(get("/api/v1/applications/" + id)))
                .andExpect(jsonPath("$.status").value("DRAFT"))
                .andExpect(jsonPath("$.version").value(1));
    }

    @Test
    void staleCompanyContextIsRejectedBeforeEffect() throws Exception {
        mvc.perform(post("/api/v1/applications")
                        .cookie(a.cookie())
                        .header("X-CSRF-Token", a.csrf())
                        .header("X-Company-Context", 99)
                        .header("Idempotency-Key", key())
                        .contentType("application/json")
                        .content(Bodies.create("company-a", 50_000_000, 12)))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("COMPANY_CONTEXT_CHANGED"));
    }
}
