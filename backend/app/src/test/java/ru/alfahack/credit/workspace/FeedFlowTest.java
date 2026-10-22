package ru.alfahack.credit.workspace;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
import java.util.*;
import com.jayway.jsonpath.JsonPath;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.web.servlet.MockMvc;
import ru.alfahack.credit.support.*;

@IntegrationTest
class FeedFlowTest {
    @Autowired MockMvc mvc;
    @Autowired JdbcClient jdbc;
    DemoClient a;
    @BeforeEach void start() throws Exception {
        jdbc.sql("TRUNCATE workspace.feed_event,workspace.feed_reaction,workspace.feed_page,workspace.feed_selection,workspace.feed_state").update();
        a=DemoClient.login(mvc,"representative-a");
    }
    String page(String suffix) throws Exception {
        return mvc.perform(a.sign(get("/api/v1/feed"+suffix).param("companyId","company-a")))
            .andExpect(status().isOk()).andReturn().getResponse().getContentAsString();
    }
    String event(String exposure,String item,String action,String eventId) throws Exception {
        return mvc.perform(a.json(post("/api/v1/recommendation-feedback"),
            "{\"clientEventId\":\""+eventId+"\",\"exposureId\":\""+exposure+"\",\"itemId\":\""+item+"\",\"action\":\""+action+"\",\"occurredAt\":\"2026-10-22T12:00:00Z\"}"))
            .andExpect(status().isOk()).andReturn().getResponse().getContentAsString();
    }
    @Test void pagesReplayWithoutDuplicateIssuanceAndPersistedSelections() throws Exception {
        String first=page("");
        List<String> one=JsonPath.read(first,"$.cards[*].contentId");
        String cursor=JsonPath.read(first,"$.nextCursor");
        String second=page("?cursor="+cursor);
        assertThat((List<String>)JsonPath.<List<String>>read(second,"$.cards[*].contentId")).doesNotContainAnyElementsOf(one);
        String replay=page("?cursor="+cursor);
        assertThat(JsonPath.<List<String>>read(replay,"$.cards[*].contentId")).isEqualTo(JsonPath.read(second,"$.cards[*].contentId"));
        assertThat(JsonPath.<String>read(replay,"$.rankingMetadata.exposureId")).isEqualTo(JsonPath.read(second,"$.rankingMetadata.exposureId"));
        assertThat(jdbc.sql("SELECT count(*) FROM workspace.feed_reaction WHERE viewed").query(Long.class).single()).isZero();
        assertThat(first).doesNotContain("score","internalReasonCodes","Service-Token");
    }
    @Test void feedbackLatestReactionSavedAndHiddenReplay() throws Exception {
        String first=page("");String cursor=JsonPath.read(first,"$.nextCursor");String second=page("?cursor="+cursor);
        String exposure=JsonPath.read(second,"$.rankingMetadata.exposureId"),item=JsonPath.read(second,"$.cards[0].contentId");
        String eventId=UUID.randomUUID().toString();
        assertThat(event(exposure,item,"HELPFUL",eventId)).isEqualTo(event(exposure,item,"HELPFUL",eventId));
        assertThat(JsonPath.<List<String>>read(page("/saved"),"$.cards[*].contentId")).containsExactly(item);
        event(exposure,item,"NOT_INTERESTED",UUID.randomUUID().toString());
        assertThat(JsonPath.<List<String>>read(page("?cursor="+cursor),"$.cards[*].contentId")).doesNotContain(item);
        assertThat(JsonPath.<List<String>>read(page("/saved"),"$.cards[*].contentId")).isEmpty();
        event(exposure,item,"HELPFUL",UUID.randomUUID().toString());
        event(exposure,item,"HELPFUL",UUID.randomUUID().toString());
        assertThat(jdbc.sql("SELECT saved_version FROM workspace.feed_state WHERE actor_id='representative-a'").query(Long.class).single()).isEqualTo(3);
        mvc.perform(a.json(post("/api/v1/recommendation-feedback"),"{\"clientEventId\":\""+eventId+"\",\"exposureId\":\""+exposure+"\",\"itemId\":\""+item+"\",\"action\":\"CLICK\",\"occurredAt\":\"2026-10-22T12:00:00Z\"}"))
            .andExpect(status().isConflict());
    }
    @Test void preferencesExpireCursorAndIsolationIsEnforced() throws Exception {
        String first=page("");String cursor=JsonPath.read(first,"$.nextCursor");
        mvc.perform(a.json(put("/api/v1/feed/preferences").param("companyId","company-a"),"{\"task\":\"EQUIPMENT\",\"help\":\"COST\"}"))
            .andExpect(status().isOk());
        mvc.perform(a.sign(get("/api/v1/feed").param("companyId","company-a").param("cursor",cursor)))
            .andExpect(status().isConflict()).andExpect(jsonPath("$.code").value("FEED_SELECTION_EXPIRED"));
        DemoClient b=DemoClient.login(mvc,"representative-b");
        mvc.perform(b.sign(get("/api/v1/feed").param("companyId","company-a"))).andExpect(status().isNotFound());
        mvc.perform(b.sign(get("/api/v1/feed").param("companyId","company-b").param("cursor",cursor))).andExpect(status().isNotFound());
        mvc.perform(a.json(put("/api/v1/feed/preferences").param("companyId","company-a"),"{\"score\":0.5}"))
            .andExpect(status().isUnprocessableContent());
        mvc.perform(get("/api/v1/feed").param("companyId","company-a").header("X-Company-Context","1")).andExpect(status().isUnauthorized());
    }
    @Test void allCandidatesEndAfterSixPagesAndVisibilityIsNotInferred() throws Exception {
        Set<String> issued=new HashSet<>();String suffix="";
        for(int i=0;i<6;i++) {
            String response=page(suffix);List<String> ids=JsonPath.read(response,"$.cards[*].contentId");
            assertThat(ids).hasSize(6);assertThat(Collections.disjoint(ids,issued)).isTrue();issued.addAll(ids);
            if(i<5)suffix="?cursor="+JsonPath.<String>read(response,"$.nextCursor");
            else assertThat(JsonPath.<Boolean>read(response,"$.hasMore")).isFalse();
        }
        assertThat(issued).hasSize(36);
    }
}
