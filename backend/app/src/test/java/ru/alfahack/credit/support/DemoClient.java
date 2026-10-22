package ru.alfahack.credit.support;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import jakarta.servlet.http.Cookie;

import com.jayway.jsonpath.JsonPath;

import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;

/** Вход синтетическим представителем и заголовки сессии для запросов API. */
public record DemoClient(Cookie cookie, String csrf, long contextVersion, String companyId) {

    public static DemoClient login(MockMvc mvc, String accountId) throws Exception {
        MvcResult result = mvc.perform(post("/demo/api/v1/session")
                        .header("Origin", "http://localhost:5173")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"accountId\":\"" + accountId + "\"}"))
                .andExpect(status().isOk())
                .andReturn();
        String body = result.getResponse().getContentAsString();
        return new DemoClient(
                result.getResponse().getCookie("credit_session"),
                JsonPath.read(body, "$.csrfToken"),
                ((Number) JsonPath.read(body, "$.contextVersion")).longValue(),
                JsonPath.read(body, "$.companyId"));
    }

    /** Cookie, CSRF и X-Company-Context. */
    public MockHttpServletRequestBuilder sign(MockHttpServletRequestBuilder request) {
        return request.cookie(cookie)
                .header("X-CSRF-Token", csrf)
                .header("X-Company-Context", contextVersion);
    }

    public MockHttpServletRequestBuilder json(MockHttpServletRequestBuilder request, String body) {
        return sign(request).contentType(MediaType.APPLICATION_JSON).content(body);
    }
}
