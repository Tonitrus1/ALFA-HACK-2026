package ru.alfahack.credit.access;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import ru.alfahack.credit.support.DemoClient;
import ru.alfahack.credit.support.IntegrationTest;

@IntegrationTest
@ActiveProfiles("selectel")
@TestPropertySource(properties="PUBLIC_ORIGIN=https://cabinet.example.com")
class SelectelAccessTest {
    @Autowired MockMvc mvc;

    @Test
    void publicHttpsOriginGetsSecureSessionCookie() throws Exception {
        var response = mvc.perform(post("/api/v1/auth/login")
                .header("Origin", "https://cabinet.example.com")
                .contentType(MediaType.APPLICATION_JSON)
                .content(DemoClient.credentials("representative-a")))
                .andExpect(status().isOk()).andReturn().getResponse();
        assertThat(response.getHeader("Set-Cookie")).contains("Secure", "HttpOnly", "SameSite=Strict");
        assertThat(response.getCookie("credit_session").getSecure()).isTrue();
    }

    @Test
    void localAndForeignOriginsAreRejectedByServerProfile() throws Exception {
        for (String origin : new String[]{"http://localhost:5173", "https://foreign.example.com"}) {
            mvc.perform(post("/api/v1/auth/login").header("Origin", origin)
                    .contentType(MediaType.APPLICATION_JSON)
                    .content(DemoClient.credentials("representative-a")))
                    .andExpect(status().isForbidden());
        }
    }
}
