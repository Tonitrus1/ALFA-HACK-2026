> В общей поставке модуль перенесён в `ml/feed_v2`; обслуживается единственным сервисом `feed`. Запуск: [корневой README](../../README.md).

# Рекомендательная лента

ML-сервис на CPU: frozen E5 или экспериментальный CatBoostRanker поверх E5-признака. Каталог v2 содержит 72 русскоязычные карточки. Профиль, кандидаты и предшествующие агрегаты реакций приходят от backend; сервис возвращает точную перестановку кандидатов и пояснения.

По умолчанию E5. CatBoost обучен на синтетических событиях и явно помечен как экспериментальный до человеческой проверки контента и разметки. Пользовательская польза на реальном трафике не установлена.

- [Текущая поставка, запуск и ограничения](../../docs/ml/feed_v2/hackathon.md).
- [Контракт событий для backend](../../docs/ml/feed_v2/analytics-contract.md).
- [Измеренные результаты](../../reports/hackathon/README.md).
- [API и правила интеграции](../../docs/ml/feed_v2/integration.md).
- [Исторические проверки E5 MVP](../../docs/ml/feed_v2/verification.md).

```sh
./scripts/feed setup
./scripts/feed prepare --download
./scripts/feed pipeline --work .local/run-01 --reports reports/run-01 --model-source .local/feed-bundle/model
./scripts/feed test --with-model --with-learned
```

После pipeline learned bundle находится в `.local/run-01/catboost`; для тестов задайте `FEED_LEARNED_TEST_BUNDLE=.local/run-01/catboost`. Для сервера выберите `FEED_RANKER=catboost` и такой же `FEED_BUNDLE`. Веса и полные датасеты остаются локальными, вне Git.

Готовая связка E5 → CatBoost запускается одной командой после задания `ML_INTERNAL_TOKEN`:

```sh
./scripts/feed serve-hybrid
```

Команда выбирает CatBoostRanker с вложенным E5 из `.local/feed-catboost`. Для bundle из pipeline: `FEED_BUNDLE=.local/run-01/catboost ./scripts/feed serve-hybrid`. E5 вычисляет similarity, общий `FeatureBuilder` объединяет его с типизированным профилем и прошлыми реакциями, CatBoost ранжирует кандидатов, затем применяется разнообразие тем. Это одна модель ранжирования поверх E5-признака; повторные ручные бонусы не прибавляются.

`./scripts/feed serve` сохраняет обычный выбор через `FEED_RANKER`, по умолчанию E5. При недоступности модели API возвращает 503 для fallback на правила в backend; пустой профиль получает RULES.

`POST /internal/v2/rankings`, `X-Service-Token`, `Idempotency-Key`, предел 100 кандидатов и формат ответа сохранены. FEED работает отдельно от Risk API на порту 8002. Backend/UI/БД и реальный сбор событий реализуют коллеги.
