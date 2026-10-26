package ru.alfahack.credit.assistant;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicReference;
import com.sun.net.httpserver.HttpServer;
import com.jayway.jsonpath.JsonPath;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import ru.alfahack.credit.support.Bodies;
import ru.alfahack.credit.support.DemoClient;
import ru.alfahack.credit.support.IntegrationTest;

/** HTTP adapter double: tests authorization/context/DB ownership, not model quality. */
@IntegrationTest
class AssistantFlowTest {
    static final AtomicReference<String> context=new AtomicReference<>();
    static final HttpServer server=start();
    static HttpServer start() {
        try {
            var s=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
            s.createContext("/v1/sessions",e->{
                String response;
                if(e.getRequestMethod().equals("GET"))response="{\"messages\":[]}";
                else {
                    String body=new String(e.getRequestBody().readAllBytes(),StandardCharsets.UTF_8);
                    if(e.getRequestURI().getPath().endsWith("/messages")) {
                        context.set(body);
                        response="{\"message_id\":\"answer\",\"status\":\"ANSWER\",\"answer\":\"Adapter test\",\"citations\":[]}";
                    } else response="{\"session_id\":\""+UUID.randomUUID()+"\",\"session_token\":\"server-only-token\"}";
                }
                byte[] bytes=response.getBytes(StandardCharsets.UTF_8);
                e.getResponseHeaders().add("Content-Type","application/json");e.sendResponseHeaders(200,bytes.length);e.getResponseBody().write(bytes);e.close();
            });s.start();return s;
        }catch(Exception ex){throw new RuntimeException(ex);}
    }
    @DynamicPropertySource
    static void settings(DynamicPropertyRegistry r) {
        r.add("credit.assistant.base-url",()->"http://127.0.0.1:"+server.getAddress().getPort());
        r.add("credit.assistant.service-token",()->"test-assistant-key-at-least-32-characters");
    }
    @AfterAll static void stop(){server.stop(0);}
    @Autowired MockMvc mvc;
    @Autowired JdbcClient jdbc;
    @Test void backendSnapshotAndConversationAreIsolatedByCompanyAndSession() throws Exception {
        var a=DemoClient.login(mvc,"representative-a");
        var b=DemoClient.login(mvc,"representative-b");
        String app=mvc.perform(a.json(post("/api/v1/applications"),Bodies.create("company-a",50_000_000,12))
            .header("Idempotency-Key",UUID.randomUUID().toString())).andExpect(status().isCreated())
            .andReturn().getResponse().getContentAsString();
        String name="test-"+UUID.randomUUID();
        String url="/api/v1/assistant/conversations/"+name+"/messages";
        mvc.perform(get(url)).andExpect(status().isUnauthorized());
        mvc.perform(a.json(post(url),"{\"clientMessageId\":\"a1\",\"text\":\"Статус заявки\"}"))
            .andExpect(status().isOk()).andExpect(jsonPath("$.answer").value("Adapter test"));
        String appId=JsonPath.read(app,"$.applicationId");
        assertThat(context.get()).contains(appId,"company-a").doesNotContain("company-b");
        mvc.perform(b.json(post(url),"{\"clientMessageId\":\"b1\",\"text\":\"Статус заявки\"}"))
            .andExpect(status().isOk());
        assertThat(context.get()).contains("company-b").doesNotContain(appId);
        assertThat(jdbc.sql("SELECT count(DISTINCT remote_id) FROM assistant.conversation WHERE conversation_id=:name")
            .param("name",name).query(Long.class).single()).isEqualTo(2);
    }
}
