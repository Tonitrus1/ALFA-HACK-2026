package ru.alfahack.credit.integration;
import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
import java.util.UUID;
import com.jayway.jsonpath.JsonPath;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.test.web.servlet.MockMvc;
import ru.alfahack.credit.integration.application.ReviewWorker;
import ru.alfahack.credit.journey.application.OutboxDispatcher;
import ru.alfahack.credit.support.*;
@IntegrationTest
class OfferCommandsFlowTest {
    @Autowired MockMvc mvc;
    @Autowired OutboxDispatcher dispatcher;
    @Autowired ReviewWorker reviews;
    String offer(DemoClient a) throws Exception {
        Journey j=new Journey(mvc,a,dispatcher,reviews);j.settle();
        String app=j.submit(50000000,DecisionFlowTest.BUSINESS,DecisionFlowTest.HEALTHY);j.settle();
        return JsonPath.read(mvc.perform(a.sign(get("/api/v1/applications/"+app+"/decision"))).andReturn().getResponse().getContentAsString(),"$.offerIds[0]");
    }
    @Test void durableCommandsReplayBeforeStateCheckAndRejectChangedKeyBody() throws Exception {
        DemoClient a=DemoClient.login(mvc,"representative-a");String id=offer(a), key=UUID.randomUUID().toString(),url="/api/v1/offers/"+id;
        var accept=a.json(post(url+"/accept"),"{\"expectedVersion\":1}").header("If-Match","\"v1\"").header("Idempotency-Key",key);
        String first=mvc.perform(accept).andExpect(status().isOk()).andExpect(jsonPath("$.status").value("ACCEPTED")).andReturn().getResponse().getContentAsString();
        mvc.perform(a.json(post(url+"/complete"),"{\"expectedVersion\":2}").header("If-Match","\"v2\"").header("Idempotency-Key",UUID.randomUUID().toString()))
            .andExpect(status().isOk()).andExpect(jsonPath("$.status").value("COMPLETED"));
        assertThat(mvc.perform(accept).andExpect(status().isOk()).andReturn().getResponse().getContentAsString()).isEqualTo(first);
        mvc.perform(a.json(post(url+"/accept"),"{\"expectedVersion\":2}").header("If-Match","\"v2\"").header("Idempotency-Key",key)).andExpect(status().isConflict());
        mvc.perform(a.sign(get(url))).andExpect(jsonPath("$.version").value(3));
        DemoClient b=DemoClient.login(mvc,"representative-b");
        mvc.perform(b.json(post(url+"/accept"),"{\"expectedVersion\":1}").header("If-Match","\"v1\"").header("Idempotency-Key",UUID.randomUUID().toString())).andExpect(status().isNotFound());
    }
    @Test void logoutRevokesCookieOnServer() throws Exception {
        DemoClient a=DemoClient.login(mvc,"representative-a");
        mvc.perform(a.sign(post("/api/v1/session/logout"))).andExpect(status().isNoContent());
        mvc.perform(a.sign(get("/api/v1/session"))).andExpect(status().isUnauthorized());
    }
}
