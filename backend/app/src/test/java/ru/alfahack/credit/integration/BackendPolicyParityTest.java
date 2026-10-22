package ru.alfahack.credit.integration;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

import ru.alfahack.credit.integration.domain.DemoPolicyV1;

import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.json.JsonMapper;

import java.util.*;

class BackendPolicyParityTest {
    static long number(Map<String, Object> data, String key) {
        return ((Number) data.get(key)).longValue();
    }

    @Test
    @SuppressWarnings("unchecked")
    void pythonAcceptanceReferenceMatchesJavaAuthority() throws Exception {
        List<Map<String, Object>> cases =
                JsonMapper.builder()
                        .build()
                        .readValue(
                                getClass().getResourceAsStream("/backend-policy.json"),
                                new TypeReference<>() {});
        for (var row : cases) {
            Map<String, Object> args = (Map<String, Object>) row.get("args"),
                    raw = (Map<String, Object>) row.get("values");
            Map<String, Long> values = new HashMap<>();
            raw.forEach((k, v) -> values.put(k, ((Number) v).longValue()));
            DemoPolicyV1.Input input =
                    new DemoPolicyV1.Input(
                            number(args, "product_min"),
                            number(args, "product_max"),
                            (int) number(args, "minimum_age"),
                            number(args, "amount"),
                            12,
                            args.get("age") == null ? null : number(args, "age"),
                            args.get("preliminary_revenue") == null
                                    ? null
                                    : number(args, "preliminary_revenue"),
                            values,
                            (boolean) args.get("already_requested"));
            Optional<Double> risk =
                    Optional.ofNullable((Number) args.get("score")).map(Number::doubleValue);
            assertThat(DemoPolicyV1.withRisk(input, risk).outcome().name())
                    .as(row.get("name").toString())
                    .isEqualTo(row.get("outcome"));
        }
    }
}
