package ru.alfahack.credit.workspace;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.core.io.ClassPathResource;

import ru.alfahack.credit.support.IntegrationTest;
import ru.alfahack.credit.workspace.application.FeedCatalog;

import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.json.JsonMapper;

import java.util.*;

@IntegrationTest
class FeedRulesParityTest {
    @Autowired FeedCatalog catalog;
    @Autowired JsonMapper json;

    @Test
    @SuppressWarnings("unchecked")
    void fallbackMatchesPythonRulesAndCatalogHash() throws Exception {
        List<Map<String, Object>> cases =
                json.readValue(
                        new ClassPathResource("feed-rules-golden.json").getInputStream(),
                        new TypeReference<>() {});
        for (var row : cases) {
            Map<String, Object> request = (Map<String, Object>) row.get("request");
            assertThat(catalog.digest).isEqualTo(request.get("catalogDigest"));
            assertThat(catalog.rules(request).get("rankedIds")).isEqualTo(row.get("rankedIds"));
        }
    }
}
