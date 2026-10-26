package ru.alfahack.credit.workspace.application;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.*;

import ru.alfahack.credit.platform.web.ApplicationException;
import ru.alfahack.credit.platform.web.ErrorKind;

import java.net.http.HttpClient;
import java.time.Duration;
import java.util.*;

@Service
public class FeedRanking {
    private final RestClient client;
    private final FeedCatalog catalog;

    public FeedRanking(
            FeedCatalog catalog,
            @Value("${credit.ml.base-url:http://localhost:8000}") String url,
            @Value("${credit.ml.service-token:}") String token) {
        this.catalog = catalog;
        JdkClientHttpRequestFactory factory =
                new JdkClientHttpRequestFactory(
                        HttpClient.newBuilder().connectTimeout(Duration.ofMillis(300)).build());
        factory.setReadTimeout(Duration.ofMillis(1700));
        client =
                RestClient.builder()
                        .baseUrl(url.isBlank() ? "http://localhost:8000" : url)
                        .requestFactory(factory)
                        .defaultHeader("X-Service-Token", token)
                        .build();
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> rank(Map<String, Object> request) {
        Map<String, Object> result;
        try {
            result =
                    client.post()
                            .uri("/internal/v2/feed/rankings")
                            .header("Idempotency-Key", request.get("requestId").toString())
                            .body(request)
                            .retrieve()
                            .body(Map.class);
        } catch (RestClientResponseException e) {
            if (e.getStatusCode().value() == 429 || e.getStatusCode().is5xxServerError())
                return catalog.rules(request);
            throw new ApplicationException(
                    ErrorKind.CONFLICT,
                    "FEED_CONTRACT_REJECTED",
                    "Контракт рекомендаций требует проверки");
        } catch (ResourceAccessException e) {
            return catalog.rules(request);
        }
        List<String> ids = (List<String>) request.get("candidateIds");
        if (result == null
                || !(result.get("rankedIds") instanceof List<?> ranked)
                || ranked.size() != ids.size()
                || new HashSet<>(ranked).size() != ids.size()
                || !new HashSet<>(ranked).equals(new HashSet<>(ids))
                || !Objects.equals(result.get("requestId"), request.get("requestId"))
                || !Objects.equals(result.get("exposureId"), request.get("exposureId"))
                || !Objects.equals(
                        result.get("candidateSetDigest"), request.get("candidateSetDigest"))
                || !Objects.equals(result.get("catalogDigest"), request.get("catalogDigest"))
                || !(result.get("explanations") instanceof Map<?, ?> explanations)
                || !explanations.keySet().equals(new HashSet<>(ids))
                || !("MODEL".equals(result.get("mode")) || "RULES".equals(result.get("mode"))))
            throw new ApplicationException(
                    ErrorKind.CONFLICT,
                    "FEED_RESULT_REJECTED",
                    "Ответ рекомендаций не прошёл проверку");
        return result;
    }
}
