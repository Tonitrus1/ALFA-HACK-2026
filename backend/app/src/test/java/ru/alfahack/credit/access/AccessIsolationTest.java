package ru.alfahack.credit.access;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import jakarta.servlet.http.Cookie;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import com.jayway.jsonpath.JsonPath;

import ru.alfahack.credit.support.IntegrationTest;

/** P03 «A/B tenant access denied»: представитель A не видит и не выбирает компанию B. */
@IntegrationTest
class AccessIsolationTest {

    static final String ORIGIN = "http://localhost:5173";

    @Autowired
    MockMvc mvc;

    @Autowired
    JdbcClient jdbc;

    record Login(Cookie cookie, String csrf, long contextVersion) {
    }

    Login login(String accountId) throws Exception {
        MvcResult result = mvc.perform(post("/api/v1/auth/login")
                        .header("Origin", ORIGIN)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(ru.alfahack.credit.support.DemoClient.credentials(accountId)))
                .andExpect(status().isOk())
                .andExpect(header().string("Cache-Control", "no-store"))
                .andReturn();
        String body = result.getResponse().getContentAsString();
        Cookie cookie = result.getResponse().getCookie("credit_session");
        assertThat(cookie).isNotNull();
        assertThat(cookie.isHttpOnly()).isTrue();
        assertThat(body).doesNotContain(cookie.getValue());
        return new Login(cookie, JsonPath.read(body, "$.csrfToken"),
                ((Number) JsonPath.read(body, "$.contextVersion")).longValue());
    }

    @Test
    void profileSelectionEndpointsAreRemoved() throws Exception {
        mvc.perform(get("/demo/api/v1/accounts"))
                .andExpect(status().isNotFound());
        mvc.perform(post("/demo/api/v1/session").header("Origin", ORIGIN)
                .contentType(MediaType.APPLICATION_JSON).content("{\"accountId\":\"representative-a\"}"))
                .andExpect(status().isNotFound());
    }

    @Test
    void operatorCannotLoginAsRepresentative() throws Exception {
        mvc.perform(post("/api/v1/auth/login")
                        .header("Origin", ORIGIN)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"login\":\"operator-demo\",\"password\":\"unknown\"}"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void wrongPasswordAndUnknownLoginDoNotIssueSessions() throws Exception {
        for (String name : new String[]{"company-a", "missing-account"}) {
            mvc.perform(post("/api/v1/auth/login").header("Origin", ORIGIN)
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("{\"login\":\"" + name + "\",\"password\":\"incorrect\"}"))
                    .andExpect(status().isUnauthorized())
                    .andExpect(jsonPath("$.code").value("INVALID_CREDENTIALS"))
                    .andExpect(header().doesNotExist("Set-Cookie"));
        }
        login("representative-a");
        String hash = jdbc.sql("SELECT password_hash FROM access.credential WHERE login='company-a'")
                .query(String.class).single();
        assertThat(hash).startsWith("pbkdf2-sha256$").doesNotContain("TestCabinet-A-2026!");
    }

    @Test
    void repeatedFailuresDoNotBlockSharedDemoLogin() throws Exception {
        for (int i = 0; i < 8; i++) {
            mvc.perform(post("/api/v1/auth/login").header("Origin", ORIGIN)
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("{\"login\":\"company-b\",\"password\":\"incorrect\"}"))
                    .andExpect(status().isUnauthorized())
                    .andExpect(jsonPath("$.code").value("INVALID_CREDENTIALS"))
                    .andExpect(jsonPath("$.message").value("Неверный логин или пароль. Проверьте данные и попробуйте снова."))
                    .andExpect(header().doesNotExist("Set-Cookie"));
        }
        login("representative-b");
        assertThat(jdbc.sql("SELECT failed_attempts FROM access.credential WHERE login='company-b'")
                .query(Integer.class).single()).isZero();
    }

    @Test
    void correctDemoPasswordClearsLegacyLockoutImmediately() throws Exception {
        jdbc.sql("UPDATE access.credential SET failed_attempts=5,locked_until=now()+interval '15 minutes' WHERE login='company-b'").update();
        try {
            login("representative-b");
            assertThat(jdbc.sql("SELECT count(*) FROM access.credential WHERE login='company-b' AND failed_attempts=0 AND locked_until IS NULL")
                    .query(Integer.class).single()).isEqualTo(1);
        } finally {
            jdbc.sql("UPDATE access.credential SET failed_attempts=0,locked_until=NULL WHERE login='company-b'").update();
        }
    }

    @Test
    void nonDemoCredentialsKeepAccountLockout() throws Exception {
        jdbc.sql("UPDATE access.credential SET login='private-b',failed_attempts=0,locked_until=NULL WHERE login='company-b'").update();
        try {
            for (int i=0;i<5;i++) {
                mvc.perform(post("/api/v1/auth/login").header("Origin", ORIGIN)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"login\":\"private-b\",\"password\":\"incorrect\"}"))
                        .andExpect(status().isUnauthorized());
            }
            String correct=ru.alfahack.credit.support.DemoClient.credentials("representative-b").replace("company-b","private-b");
            mvc.perform(post("/api/v1/auth/login").header("Origin",ORIGIN)
                    .contentType(MediaType.APPLICATION_JSON).content(correct))
                    .andExpect(status().isUnauthorized());
            assertThat(jdbc.sql("SELECT count(*) FROM access.credential WHERE login='private-b' AND locked_until>now()")
                    .query(Integer.class).single()).isEqualTo(1);
        } finally {
            jdbc.sql("UPDATE access.credential SET login='company-b',failed_attempts=0,locked_until=NULL WHERE login='private-b'").update();
        }
    }

    @Test
    void loginRequiresExactOrigin() throws Exception {
        mvc.perform(post("/api/v1/auth/login")
                        .header("Origin", "http://evil.example")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(ru.alfahack.credit.support.DemoClient.credentials("representative-a")))
                .andExpect(status().isForbidden());
        mvc.perform(post("/api/v1/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(ru.alfahack.credit.support.DemoClient.credentials("representative-a")))
                .andExpect(status().isForbidden());
    }

    @Test
    void sessionSelectsTheOnlyCompany() throws Exception {
        Login a = login("representative-a");

        mvc.perform(get("/api/v1/session").cookie(a.cookie()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.userId").value("representative-a"))
                .andExpect(jsonPath("$.companyId").value("company-a"))
                .andExpect(jsonPath("$.contextVersion").value(1));
    }

    @Test
    void representativeSeesOnlyOwnCompany() throws Exception {
        Login a = login("representative-a");

        mvc.perform(get("/api/v1/companies").cookie(a.cookie()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items.length()").value(1))
                .andExpect(jsonPath("$.items[0].companyId").value("company-a"))
                .andExpect(jsonPath("$.items[0].roles[0]").value("REPRESENTATIVE"));
        mvc.perform(get("/api/v1/companies/company-a").cookie(a.cookie()))
                .andExpect(status().isOk());
    }

    @Test
    void foreignCompanyIsIndistinguishableFromMissing() throws Exception {
        Login a = login("representative-a");

        String foreign = mvc.perform(get("/api/v1/companies/company-b").cookie(a.cookie()))
                .andExpect(status().isNotFound())
                .andReturn().getResponse().getContentAsString();
        String missing = mvc.perform(get("/api/v1/companies/company-zzz").cookie(a.cookie()))
                .andExpect(status().isNotFound())
                .andReturn().getResponse().getContentAsString();

        assertThat((String) JsonPath.read(foreign, "$.code")).isEqualTo(JsonPath.read(missing, "$.code"));
        assertThat((String) JsonPath.read(foreign, "$.message")).isEqualTo(JsonPath.read(missing, "$.message"));
    }

    @Test
    void cannotSelectForeignCompany() throws Exception {
        Login a = login("representative-a");

        mvc.perform(selectCompany(a, "company-b", a.contextVersion()))
                .andExpect(status().isNotFound());
        mvc.perform(get("/api/v1/session").cookie(a.cookie()))
                .andExpect(jsonPath("$.companyId").value("company-a"))
                .andExpect(jsonPath("$.contextVersion").value(1));
    }

    @Test
    void selectingCompanyRotatesContextAndCsrf() throws Exception {
        Login a = login("representative-a");

        String body = mvc.perform(selectCompany(a, "company-a", a.contextVersion()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.contextVersion").value(2))
                .andReturn().getResponse().getContentAsString();
        assertThat((String) JsonPath.read(body, "$.csrfToken")).isNotEqualTo(a.csrf());

        // Старый контекст и старый CSRF больше не принимаются.
        mvc.perform(selectCompany(a, "company-a", 1)).andExpect(status().isForbidden());
        Login rotated = new Login(a.cookie(), JsonPath.read(body, "$.csrfToken"), 2);
        mvc.perform(selectCompany(rotated, "company-a", 1))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("COMPANY_CONTEXT_CHANGED"));
    }

    @Test
    void requestsWithoutSessionAreRejected() throws Exception {
        mvc.perform(get("/api/v1/session")).andExpect(status().isUnauthorized());
        mvc.perform(get("/api/v1/companies").cookie(new Cookie("credit_session", "forged")))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.correlationId").isNotEmpty());
    }

    @Test
    void mutationWithoutCsrfIsForbidden() throws Exception {
        Login a = login("representative-a");

        mvc.perform(post("/api/v1/session/company")
                        .cookie(a.cookie())
                        .header("X-Company-Context", a.contextVersion())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"companyId\":\"company-a\"}"))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("CSRF_TOKEN_INVALID"));
    }

    @Test
    void bumpingAuthEpochRevokesSessions() throws Exception {
        Login b = login("representative-b");
        mvc.perform(get("/api/v1/session").cookie(b.cookie())).andExpect(status().isOk());

        jdbc.sql("UPDATE access.actor SET auth_epoch = auth_epoch + 1 WHERE actor_id = 'representative-b'").update();

        mvc.perform(get("/api/v1/session").cookie(b.cookie())).andExpect(status().isUnauthorized());
        mvc.perform(get("/api/v1/session").cookie(login("representative-b").cookie())).andExpect(status().isOk());
    }

    @Test
    void reloginRevokesPreviousBrowserSession() throws Exception {
        Login first = login("representative-a");
        MvcResult second = mvc.perform(post("/api/v1/auth/login")
                        .cookie(first.cookie())
                        .header("Origin", ORIGIN)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(ru.alfahack.credit.support.DemoClient.credentials("representative-a")))
                .andExpect(status().isOk())
                .andReturn();

        mvc.perform(get("/api/v1/session").cookie(first.cookie())).andExpect(status().isUnauthorized());
        mvc.perform(get("/api/v1/session").cookie(second.getResponse().getCookie("credit_session")))
                .andExpect(status().isOk());
    }

    private static org.springframework.test.web.servlet.RequestBuilder selectCompany(
            Login login, String companyId, long contextVersion) {
        return post("/api/v1/session/company")
                .cookie(login.cookie())
                .header("X-CSRF-Token", login.csrf())
                .header("X-Company-Context", contextVersion)
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"companyId\":\"" + companyId + "\"}");
    }
}
