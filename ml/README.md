# Локальный ML скоринг

> **Интеграционная поставка 22.10.2026:** backend + реальные Risk/Feed, ML bridge и Compose. Текущая архитектура, запуск и ограничения: [руководство интеграции](../docs/integration-mvp.md). Исторические описания ниже относятся к исходным веткам и не подтверждают этот runtime.


Реализованы обучение логистической регрессии и CatBoost с ограниченным вложенным подбором, общий feature-builder, Risk API v2, PostgreSQL snapshots/inference и сценарный CLI. Данные и классы полностью синтетические; результат BANKRUPTCY_PROXY / DEMONSTRATION / DEMO_RESEARCH, не банковская PD. Прежний CatBoost/Optuna bundle сохранён как рабочая версия и для отката.

Из корня подготовленного репозитория:

```sh
./scripts/demo up --offline
./scripts/demo scenarios
./scripts/demo test
```

Полная инструкция подготовки, API, policy и передачи backend/UI-разработчикам: [ML integration](../docs/ml-integration.md).

- `scoring/features.py` — восемь коэффициентов, Decimal-конвертация и проверки.
- `scoring/train.py`, `learning.py` — повторная внешняя CV и внутренний подбор только на train; preprocessing внутри модели; отдельный кандидат без публикации.
- `scoring/bundle.py`, `releases.py` — проверка артефактов, совместимость восьми признаков и явное переключение/откат.
- `scoring/evaluation.py` — общие финансовые правила, метрики и диагностический порог ручной проверки.
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

После скачивания этой ветки датасет и обученная модель уже доступны локально. На macOS arm64 выполните `./scripts/setup-ml.sh`, затем `./scripts/demo up --offline`. Установка зависимостей требует сеть; запуск не требует переобучения. Для нового кандидата: `./scripts/demo train --folds 5 --repeats 3 --threads 2 --output ../output/my-scoring-candidate` — каталог должен быть новым. По умолчанию данные читаются из `datasets/ru-sme-dataset-10000`; другой путь задаётся `--dataset` либо `DATASET_PATH`. Переобучение не заменяет рабочий bundle, fixtures или reports.

Текущий выбор: `./scripts/demo active`. Явное переключение проверенного выпуска: `./scripts/demo activate --bundle <каталог>`; откат: `./scripts/demo activate --bundle ml/artifacts/baseline`. После смены требуется перезапуск сервиса и получение нового bundleDigest клиентом. Кандидат без независимого подтверждения и проверки API не активируется. Подробности и ограничения порога 5% — в инструкции интеграции.

UI и backend-процесс заявки — задачи интеграторов. Основная модель не читает названия сценариев и expectedOutcome. Runtime не обучает модель и не скачивает артефакты.

## Рекомендательная лента

Отдельный модуль [feed/](feed/README.md): локальная multilingual-e5-small, каталог 36 карточек и внутренний Feed Ranking API. Запуск `./scripts/feed serve`, отдельная `.venv-feed`, порт 8002. Подготовка, контракты и примеры для коллег: [feed-integration](../docs/feed-integration.md).


Сохранённый [evaluated-candidate](artifacts/scoring-v2-351935cfd80c/) логрега и [evidence](experiments/scoring-v2-351935cfd80c/README.md) доступны в checkout. Строгий gate превосходства не выполнен (`qualityGatePassed=false`), активным остаётся baseline. `.venv/bin/python scripts/replay_scoring_evidence.py` из корня checkout проверяет hashes/disjointness и пересчитывает сохранённые метрики и парный bootstrap без сети, БД, обучения или активации. Replay — не новая независимая проверка; все исходы синтетические. Исторические исходники лежат в evidence `archive/*.txt` только для provenance. Новое обучение должно писать в отдельный offline-каталог: всё дерево `ml/artifacts/` защищено, включая новые подпапки и symlink.
