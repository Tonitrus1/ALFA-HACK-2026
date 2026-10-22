# Модель скоринга и качество

Назначение: модель скоринга и качество.

Статус реализации: отдельный локальный ML-сервис; публичный backend и frontend не поставляются. Статус проверки документации — в [verification.md](verification.md).

Актуальность: 22.10.2026. Исходный проверяемый снимок: `ml/local-scoring-runtime` / [`f14d090a956d`](https://github.com/Tonitrus1/ALFA-HACK-2026/commit/f14d090a956d2a9063da57a53c269237b5df6298). Среда исторических runtime-проверок: macOS arm64, Python 3.12.13. При этой миграции сервисы повторно не запускались.

## Назначение и допустимое использование

Технический демонстрационный proxy банкротства на вымышленных финансовых данных. Результат `BANKRUPTCY_PROXY / DEMONSTRATION / DEMO_RESEARCH`. Это не банковская PD, не оценка реальных компаний и не основание для автоматического кредитного решения.

## Активные компоненты

Активный CatBoostClassifier: `catboost-optuna-v1`. Источник алгоритма — CatBoost, Apache-2.0 по metadata установленного пакета; обученные веса получены внутри проекта. [Manifest](../../../ml/artifacts/baseline/manifest.json), [model.joblib](../../../ml/artifacts/baseline/model.joblib), [артефактная model card](../../../ml/artifacts/baseline/model-card.md), [schema признаков](../../../ml/artifacts/baseline/feature-schema.json), [SHA256SUMS](../../../ml/artifacts/baseline/SHA256SUMS). Хешируемые файлы не переписаны при унификации.

Preprocessing — общий builder восьми коэффициентов, `nan_mode=Min`; imputer/scaler отсутствуют. Полные параметры и версии пакетов читаются из manifest/selection-lock. Точное значение bundleDigest: `56b30e55f012515557beba0f80d51fe27cf5cffeb9fb511965a72ba03266ab2e`.

Отдельный неактивный кандидат, gate и механизм activate отсутствуют в исходном снимке этой ветки. Описанные стандартом более поздние кандидаты интеграционной ветки не являются активной моделью здесь и не поставляются вместе с этим оформлением.

## Данные и протокол обучения

[Описание набора](data.md). Train=7016/352 событий, validation=1494/80, test=1490/80. Компании между частями не пересекаются; используется поставленный split. Финансы и labels полностью синтетические. Реестр реальных ООО, hybrid и truth-файл не используются как признаки/источники обучения.

Optuna TPE(seed=42): 30 trials, 3-fold StratifiedKFold на train, objective — средняя Average Precision; MedianPruner. Early stopping внутри folds по Logloss; финальные iterations — медиана fold tree counts. Пять лучших завершённых trials переобучаются на train, версия выбирается по validation AP. [История study](../../../reports/optuna-study.json). Model/policy/study фиксируются в [selection-lock](../../../ml/artifacts/baseline/selection-lock.json) до открытия test. Калибровка не применялась.

## Метод оценки и критерий выпуска

Отдельная test evaluation после выбора, без подбора параметров/порога по test. Сценарные seed-примеры выбираются из train. Локальный критерий выбора — validation AP, а не доказательство преимущества над всеми baseline. Банковского release gate в этом снимке нет. Политика `synthetic-demo-policy-3` выбирает демонстрационный бюджет ручной проверки на пригодных validation-примерах; это не риск-норматив.

## Результаты

Исторический отчёт 21.10.2026, `catboost-optuna-v1`, 1490 test-строк/80 искусственных событий: [evaluation.json](../../../reports/evaluation.json).

| Метрика | Значение |
|---|---|
| ROC-AUC | 0.904486 |
| Average Precision | 0.405604 |
| Brier | 0.039988 |
| Log loss | 0.143474 |
| Prevalence | 0.053691 |

Полные confusion matrix и квантили score — в отчёте. Порог ручной проверки — в [policy](../../../ml/artifacts/baseline/policy.json), не копируйте его в UI. При документационной миграции метрики повторно не измерялись.

## Ограничения и непроверенные свойства

Одна искусственная выборка; перенос на реальных российских заёмщиков, PD-калибровка, банковская пригодность и production-нагрузка не подтверждены. Score не зависит от суммы запроса; уменьшение суммы не обходит высокий риск. Альтернативная оферта — обязанность backend policy. Нет утверждения, что обновлённый CatBoost лучше исторической логистической модели по всем метрикам.

## Обновление, совместимость и откат

[Operations](operations.md): проверка hashes/версий, отдельное обучение и ограничения ручного переключения. Автоматического safe activate/rollback в этой ветке нет.
