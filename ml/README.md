# Локальный ML скоринг

Реализованы обучение baseline, общий feature-builder, Risk API v2, PostgreSQL snapshots/inference и сценарный CLI. Данные и классы полностью синтетические; результат BANKRUPTCY_PROXY / DEMONSTRATION / DEMO_RESEARCH, не банковская PD.

Из корня подготовленного репозитория:

```sh
./scripts/demo up --offline
./scripts/demo scenarios
./scripts/demo test
```

Полная инструкция подготовки, API, policy и передачи backend/UI-разработчикам: [ML integration](../docs/ml-integration.md).

- `scoring/features.py` — восемь коэффициентов, Decimal-конвертация и проверки.
- `scoring/train.py` — offline обучение, сохранённый split, честная test evaluation.
- `scoring/server.py` — настоящий HTTP inference, внутренний токен, долговечные записи.
- `scoring/client.py` — интеграционный клиент-пример.
- `scoring/demo_policy.py` — исполняемый эталон policy для переноса в backend.
- `fixtures/` — маленькие вымышленные примеры, ожидания только для тестов.
- `examples/` — фактические запросы и ответы API.
- `migrations/` — отдельная ML-схема PostgreSQL; runtime-роль без UPDATE/DELETE.
- [Отчёты](../reports/) — metrics, policy, сценарии и runtime; веса исключены из Git.

UI и backend-процесс заявки — задачи интеграторов. Основная модель не читает названия сценариев и expectedOutcome. Runtime не обучает модель и не скачивает артефакты.
