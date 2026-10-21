# Локальный ML скоринг

Реализованы обучение CatBoost с Optuna, общий feature-builder, Risk API v2, PostgreSQL snapshots/inference и сценарный CLI. Данные и классы полностью синтетические; результат BANKRUPTCY_PROXY / DEMONSTRATION / DEMO_RESEARCH, не банковская PD.

Из корня подготовленного репозитория:

```sh
./scripts/demo up --offline
./scripts/demo scenarios
./scripts/demo test
```

Полная инструкция подготовки, API, policy и передачи backend/UI-разработчикам: [ML integration](../docs/ml-integration.md).

- `scoring/features.py` — восемь коэффициентов, Decimal-конвертация и проверки.
- `scoring/train.py` — CatBoostClassifier, Optuna TPE, CV на train, выбор по validation и отдельная test evaluation.
- `scoring/server.py` — настоящий HTTP inference, внутренний токен, долговечные записи.
- `scoring/client.py` — интеграционный клиент-пример.
- `scoring/demo_policy.py` — исполняемый эталон policy для переноса в backend.
- `fixtures/` — маленькие вымышленные примеры, ожидания только для тестов.
- `examples/` — фактические запросы и ответы API.
- `migrations/` — отдельная ML-схема PostgreSQL; runtime-роль без UPDATE/DELETE.
- [Обученная модель](artifacts/baseline/) — CatBoost и веса `model.joblib`, manifest, policy, evaluation, model card и SHA256SUMS.
- [Датасет](../datasets/ru-sme-dataset-10000/DATASET_README_RU.md) — полный исходный комплект и train/validation/test; для обучения используются только полностью синтетические файлы `training_simulation` и `simulation_splits/`.
- `generated/companies.json` — подготовленные синтетические компании для локальных тестов; те же сценарии опубликованы в `fixtures/`.
- [Отчёты](../reports/) — metrics, policy, сценарии и runtime.

После скачивания этой ветки датасет и обученная модель уже доступны локально. На macOS arm64 выполните `./scripts/setup-ml.sh`, затем `./scripts/demo up --offline`. Установка зависимостей требует сеть; запуск не требует переобучения. Для отдельного переобучения: `./scripts/demo train --trials 30 --folds 3 --threads 4` — по умолчанию используется `datasets/ru-sme-dataset-10000` внутри репозитория; другой путь задаётся `--dataset` либо `DATASET_PATH`.

UI и backend-процесс заявки — задачи интеграторов. Основная модель не читает названия сценариев и expectedOutcome. Runtime не обучает модель и не скачивает артефакты.
