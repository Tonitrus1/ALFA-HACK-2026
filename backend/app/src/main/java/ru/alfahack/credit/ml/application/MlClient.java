package ru.alfahack.credit.ml.application;

/**
 * Транспорт к ML-сервису. HTTP-реализация вызывает internal v2 API с X-Service-Token и бюджетами времени;
 * контрактный двойник отвечает детерминированно по тем же схемам до готовности моделей. Любой сбой — исключение.
 */
public interface MlClient {

    String mode();

    MlContracts.FeatureSnapshot createFeatureSnapshot(String idempotencyKey, MlContracts.FeatureSnapshotInput input);

    MlContracts.RiskResult evaluateRisk(String idempotencyKey, MlContracts.RiskRequest request);

    MlContracts.RankingResult rank(String idempotencyKey, MlContracts.RankingRequest request);

    MlContracts.AssistantResponse answer(MlContracts.RagInput input);
}
