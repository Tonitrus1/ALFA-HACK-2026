package ru.alfahack.credit.ml.infrastructure;

import java.net.http.HttpClient;
import java.time.Duration;

import org.springframework.http.MediaType;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

import ru.alfahack.credit.ml.application.MlClient;
import ru.alfahack.credit.ml.application.MlContracts;

/**
 * Клиент internal v2 API ML-сервиса. Отдельные бюджеты: признаки/ранжирование 2 с, риск 3 с, RAG 60 с.
 * Секрет X-Service-Token не логируется; ответы ML проверяют шлюзы приложения.
 */
class HttpMlClient implements MlClient {

    private final RestClient fast;
    private final RestClient risk;
    private final RestClient generation;

    HttpMlClient(String baseUrl, String serviceToken) {
        this.fast = client(baseUrl, serviceToken, Duration.ofSeconds(2));
        this.risk = client(baseUrl, serviceToken, Duration.ofSeconds(3));
        this.generation = client(baseUrl, serviceToken, Duration.ofSeconds(60));
    }

    private static RestClient client(String baseUrl, String serviceToken, Duration readTimeout) {
        HttpClient http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(1)).build();
        JdkClientHttpRequestFactory factory = new JdkClientHttpRequestFactory(http);
        factory.setReadTimeout(readTimeout);
        return RestClient.builder()
                .baseUrl(baseUrl)
                .requestFactory(factory)
                .defaultHeader("X-Service-Token", serviceToken)
                .build();
    }

    @Override
    public String mode() {
        return "MODEL";
    }

    @Override
    public MlContracts.FeatureSnapshot createFeatureSnapshot(
            String idempotencyKey, MlContracts.FeatureSnapshotInput input) {
        return fast.post().uri("/internal/v2/feature-snapshots")
                .header("Idempotency-Key", idempotencyKey)
                .contentType(MediaType.APPLICATION_JSON)
                .body(input)
                .retrieve()
                .body(MlContracts.FeatureSnapshot.class);
    }

    @Override
    public MlContracts.RiskResult evaluateRisk(String idempotencyKey, MlContracts.RiskRequest request) {
        return risk.post().uri("/internal/v2/risk/evaluations")
                .header("Idempotency-Key", idempotencyKey)
                .contentType(MediaType.APPLICATION_JSON)
                .body(request)
                .retrieve()
                .body(MlContracts.RiskResult.class);
    }

    @Override
    public MlContracts.RankingResult rank(String idempotencyKey, MlContracts.RankingRequest request) {
        return fast.post().uri("/internal/v2/rankings")
                .header("Idempotency-Key", idempotencyKey)
                .contentType(MediaType.APPLICATION_JSON)
                .body(request)
                .retrieve()
                .body(MlContracts.RankingResult.class);
    }

    @Override
    public MlContracts.AssistantResponse answer(MlContracts.RagInput input) {
        return generation.post().uri("/internal/v2/assistant/answers")
                .contentType(MediaType.APPLICATION_JSON)
                .body(input)
                .retrieve()
                .body(MlContracts.AssistantResponse.class);
    }
}
