# Передача ML-модуля разработчикам backend и UI

Актуально на 21 октября 2026. Объём этой поставки после уточнения задачи: **обученная модель, настоящий Risk API, PostgreSQL-хранилище снимков/inference, шесть воспроизводимых сценариев и документация интеграции**. UI и жизненный цикл кредитной заявки реализуют другие разработчики.

## 1. Что умеет модель

Модель считает непрерывный `score` от 0 до 1 по восьми отношениям финансовой отчётности. Алгоритм: `SimpleImputer(strategy=median, add_indicator=True) → StandardScaler → LogisticRegression`. Код преобразования общий для обучения и serving: `ml/scoring/features.py`.

Назначение результата строго `BANKRUPTCY_PROXY / DEMONSTRATION / DEMO_RESEARCH`. Компании, финансы и целевая переменная полностью вымышлены. Это не банковская PD, не оценка настоящих российских компаний и не обещание кредита.

Модель не возвращает APPROVED/DECLINED. Эти маршруты выбирает backend policy. Исполняемый эталон для переноса и проверки интеграции: `ml/scoring/demo_policy.py`; он не изменяет заявки и не выпускает оферты. Сценарный CLI объединяет настоящие ML-вызовы с этим эталоном, чтобы разработчик мог воспроизвести маршруты заранее.

## 2. Запуск

Подготовленный стенд на этом компьютере, из корня репозитория:

```sh
./scripts/demo up --offline
```

Сервис: `http://127.0.0.1:8001`. Java, Node, браузер и frontend для этого не нужны. Если сервис уже работает, останавливать его перед повторным запуском: `./scripts/demo down`.

Проверка сценариев и тестов:

```sh
./scripts/demo scenarios
./scripts/demo test
PYTHONPATH=ml .venv/bin/python scripts/verify_ml_runtime.py
```

Сценарии используют настоящий HTTP inference и долговечные записи PostgreSQL. Прогон добавляет синтетические снимки/inference и не удаляет прошлые. `verify_ml_runtime.py` перезапускает только выделенный ML-стенд, проверяет восстановление и моделирует отказ записи.

Первичная установка на macOS arm64 (нужны сеть, Python 3.12, инструменты сборки Apple):

```sh
./scripts/setup-ml.sh
./scripts/demo train --dataset /Users/user/Documents/Alfa_hack/datasets/ru-sme-dataset-10000
./scripts/demo up --offline
```

Путь на другом компьютере задаётся `--dataset` либо `DATASET_PATH`; сеть нужна для первой установки Python-пакетов и подготовки PostgreSQL, обучение читает только локальные файлы. Native launcher проверен на macOS arm64; Linux/Windows и контейнеры не проверялись. Для другого deployment разработчик может запустить `uvicorn scoring.server:app` с переменными ниже и собственной PostgreSQL 17.

Раздельные команды: `./scripts/demo migrate` создаёт **credit_scoring_demo** и применяет SQL из `ml/migrations`; `./scripts/demo train` обучает offline; `./scripts/demo scenarios` читает маленькие fixtures. Отдельный seed БД не нужен: финансовые примеры хранятся в `ml/fixtures/scenarios.json`, сервер не читает их при inference.

Безопасный сброс:

```sh
./scripts/demo reset --confirm credit_scoring_demo
./scripts/demo up --offline
```

Сброс очищает только `ml.features` и `ml.inferences` в выделенной локальной БД. Проверяются фиксированные имя/адрес БД, маркер кластера и владелец проекта. Артефакты/fixtures/датасет сохраняются. Произвольный DSN для reset не принимается.

## 3. Настройка и секреты

Локальный launcher генерирует `.local/runtime.json` с правами 0600; файл исключён из Git. Не копировать токен в frontend. Для ручного запуска backend/ML:

| Переменная | Значение / смысл |
| --- | --- |
| `PYTHONPATH` | абсолютный путь к `ml` |
| `MODEL_BUNDLE` | путь к подготовленному `ml/artifacts/baseline` |
| `ML_DATABASE_URL` | PostgreSQL DSN роли, имеющей только SELECT/INSERT в `ml` |
| `ML_INTERNAL_TOKEN` | общий служебный токен backend → ML |
| `OPENBLAS_NUM_THREADS`, `OMP_NUM_THREADS` | `1` для воспроизводимого локального CPU-стенда |

Все реализованные endpoints, включая `/health`, требуют `Authorization: Bearer <ML_INTERNAL_TOKEN>`. Порт слушает только loopback. При отдельном размещении сервисов инженер отвечает за сетевую изоляцию/аутентификацию и передаёт backend токен через секреты deployment. Браузер вызывает backend.

## 4. Контракт вызова

Каноническая спецификация: `docs/architecture/contracts/internal.openapi.json`. Ограничения реализованного ML-профиля перечислены в `local-risk-profile.json`. Точная runtime-схема запросов доступна в `/openapi.json`. Остальные операции большого HACKATHON-1.5 контракта остаются спецификацией.

1. Backend сохраняет подтверждённый неизменяемый финансовый снимок и пакет отправки. Передаёт точную копию финансового блока в **POST `/internal/v2/feature-snapshots`**.
2. ML проверяет финансовые значения, digest и временную доступность; сохраняет неизменяемый FeatureSnapshot. **GET `/internal/v2/feature-snapshots/{id}`** читает именно эту версию.
3. Backend вызывает **POST `/internal/v2/risk/evaluations`** с ID/digest снимка, схемой 2, закреплённым bundleDigest и requestId попытки.
4. ML возвращает результат только после commit inference record. Backend отдельно применяет policy к своим закреплённым данным и условиям заявки.
5. **GET `/internal/v2/bundle`** возвращает manifest и подготовленную policy с T_manual. Закреплять эти версии на попытку; изменение bundle требует перепроверки policy и fixtures.

Полные работающие примеры запросов и фактических ответов лежат в `ml/examples/`. UUID в ответах относятся к выполненному прогону; после reset сначала создаётся новый снимок. Python-клиент для интеграционного примера: `ml/scoring/client.py`.

Пример создания признаков (`financialStatement` полностью приведён в examples):

```json
{
  "applicationId": "DEMO:application-1",
  "submissionSnapshotId": "submission-1",
  "financialSnapshotId": "financial-1",
  "financialSnapshotDigest": "<SHA-256 канонического financialStatement>",
  "financialStatementVersion": 1,
  "asOf": "2026-10-21T00:00:00Z",
  "latestSourceAvailableAt": "2026-04-01T00:00:00Z",
  "purpose": "DEMO_RESEARCH",
  "financialStatement": "<объект из ml/examples/create-feature.request.json>"
}
```

Это структурное пояснение с placeholders; для исполнения использовать JSON-файлы в `ml/examples`. Даты ISO-8601 с timezone. Период отчётности в этом bundle: 01.01.2025–31.12.2025; дата доступности должна следовать после периода и быть не позже asOf.

Risk request:

```json
{
  "requestId": "attempt-1",
  "featureSnapshotId": "<ID ответа feature API>",
  "featureSnapshotDigest": "<snapshotDigest ответа>",
  "featureSchemaVersion": 2,
  "bundleDigest": "<bundleDigest из manifest>",
  "purpose": "DEMO_RESEARCH"
}
```

Успешный ответ содержит `requestId`, `inferenceId`, `featureSnapshotId`, `featureSnapshotDigest`, `bundleDigest`, `modelVersion`, `releaseId`, `score`, `scoreKind`, `calibrationStatus`, `purpose`, `internalReasonCodes`. `releaseId` в исследовательском профиле равен версии локального bundle; он не означает одобрение банковского релиза.

### Повторы, ошибки и дедлайны

`(submissionSnapshotId, featureCodeDigest)` — идемпотентная идентичность feature input. Повтор точного тела возвращает исходный snapshot; иное тело с той же идентичностью даёт 409. `requestId` — ключ одной оценки: то же тело возвращает исходный inferenceId/score; другое тело даёт 409. Конкурентные повторы защищены блокировкой и уникальными ограничениями PostgreSQL.

| HTTP / отказ | Действие интегратора |
| --- | --- |
| 403 | Исправить служебную аутентификацию; не ретраить из браузера |
| 404 | Проверить точный ID снимка |
| 409 | Проверить digest/закреплённый bundle и повтор ключа с другим телом |
| 422 | Исправить формат, финансовые данные, purpose, schema или время доступности |
| timeout / 5xx / нет долговечной записи | Видимый MANUAL в backend, без score=0 |

Risk budget — 3 секунды. Backend должен ограничить общий deadline, включая feature-вызов, очередь и фиксацию fallback. Пример клиента задаёт сетевой timeout каждому запросу; production-адаптер backend должен учитывать оставшееся общее время. При сетевой неопределённости повторять исходное тело с исходным requestId. Создание нового requestId не является retry.

Запоздалый ответ не должен менять отменённую/заменённую попытку или автоматически выпускать оферту после fallback MANUAL. Это CAS/state-machine обязанность backend; ML не имеет доступа к его таблицам. Хранение application/session/outbox, RFI amendment, оферт и принятия не входит в реализацию ML.

## 5. Финансовые поля и точность

API принимает **целые копейки**, не float-рубли. Восемь обязательных полей:

| Поле API | Коэффициент |
| --- | --- |
| totalAssetsMinor | знаменатель активов |
| currentAssetsMinor | X3, X4 |
| totalLiabilitiesMinor | X2, X8 |
| currentLiabilitiesMinor | X3, X4 |
| equityMinor | X8, X10 |
| revenueMinor | X9 и cap backend policy |
| netProfitMinor | X1 |
| ebitMinor | X7 |

X1=profit/assets; X2=liabilities/assets; X3=(currentAssets−currentLiabilities)/assets; X4=currentAssets/currentLiabilities; X7=EBIT/assets; X8=equity/liabilities; X9=revenue/assets; X10=equity/assets. Все признаки считаются сервером. Запрос с ручными features/target/score не принимается.

Исходные рубли из Parquet конвертируются Decimal → int, без промежуточного float. Диапазон денег: ±9007199254740991 копейка; отрицательные капитал/прибыль/EBIT допустимы. Assets>0; текущие части не больше итогов; баланс assets=liabilities+equity с явным допуском **1 копейка**. Валюта RUB, стандарт DEMO. Пустое значение не ноль; обязательная форма до submit должна быть полностью заполнена и подтверждена backend.

При нулевых обязательствах X4/X8 дают `null`, затем median imputation. В текущем train отсутствовали missing ratios, поэтому scikit-learn `add_indicator=True` не обучил отдельных indicator-колонок; новые пропуски обрабатываются медианами. Это ограничение исследовательского bundle, отдельно проверенное для нулевого долга; качество на таких реальных компаниях не оценивалось.

Digest: SHA-256 UTF-8 JSON, ключи объектов рекурсивно сортируются, без пробелов, `ensure_ascii=False`, без NaN/Infinity. Financial digest считается от точного `financialStatement`. Snapshot digest — от всех полей FeatureSnapshot кроме самого `snapshotDigest`; ID/версии/время входят в hash. Backend может хранить snapshotDigest, возвращённый ML, и передавать его без повторной сериализации вещественных коэффициентов.

## 6. Policy и сценарии

Порог T_manual=**0.03908894142283073**, версия policy **synthetic-demo-policy-2**. Это верхние 20% score среди пригодных validation-примеров для оборотного продукта: 1205 пригодных, 241 на ручную проверку; 38 искусственных событий среди пригодных, 25 среди направленных на проверку; на границе один score. Норматив банка из этого не следует.

Приоритет: ошибка данных → существенное расхождение выручки с reference → жёсткая продуктовая пригодность → отрицательный капитал/долг ≥90% активов → нулевая выручка/неподдерживаемый случай → сбой ML → score≥T_manual → превышение cap → одобрение. Точный эталон в `demo_policy.py` и `local-demo-policy.json`.

cap = min(product.maxAmountMinor, revenueMinor // 4). Ниже минимума продукта оферта не создаётся: MANUAL. Высокий score всегда раньше ALTERNATIVE. Изменение суммы не меняет финансовый score.

| Сценарий | Данные / действие | Проверенный результат |
| --- | --- | --- |
| S01 | Согласованные источники, низкий настоящий score, 200 тыс. RUB | APPROVED |
| S02 | Корректный баланс, обязательства 95% активов | DECLINED до вызова модели |
| S03 | Выручка в декларации ×2 против reference | NEEDS_INFO; коррекция выручки в новом снимке → настоящий inference → APPROVED |
| S04 | Финансы S01, запрос 5 000 000,01 RUB | ALTERNATIVE на допустимую сумму |
| S05 | Другой train-пример, проходящий жёсткие правила, высокий настоящий score | MANUAL |
| S06 | Применимые данные, отказ именно вызова risk после создания признаков | MANUAL без score/inferenceId |

S06 использует явный fault в сценарном клиенте: только risk-запрос конкретной попытки направляется на закрытый локальный порт. Рабочий ML API не читает scenarioId/expectedOutcome и не содержит переключателя подготовленных score. После сценария обычные вызовы продолжают работать.

`ml/fixtures/scenarios.json` содержит маленькие вымышленные входные данные, закреплённый bundleDigest и происхождение из train. `expectations.json` читает только тестовый/сценарный runner. Переименование карточки или изменение допустимых финансов не фиксирует маршрут: исход снова вычисляется. Для RFI backend хранит исходную reference-версию; коррекция создаёт amendment и новую попытку, исходный пакет неизменяем.

CLI проверяет путь до решения policy. REVIEW/ACCEPTED/COMPLETED, операторское решение, expiry/cancel и банковские оферты описаны для реализации коллегами; из наличия ML-сценария они не считаются готовыми.

## 7. Обучение, артефакты и фактическая проверка

Данные: только `training_simulation.parquet` / `simulation_splits/*.parquet`. Сохранён split train=7016/352 событий, validation=1494/80, test=1490/80. Прежний UCI/60/20/20 заменён этим поставленным синтетическим разделением. Hybrids/реальные ИНН и файл `simulation_truth_DO_NOT_USE_AS_FEATURES` не открываются для обучения/подбора/демо-примеров.

Подбор C∈{0.01,0.1,1,10}: CV на train, версия по validation Average Precision; preprocessing fit только train. Файлы model/policy фиксируются в `selection-lock.json` до чтения test. Test не используется для выбора сценариев. Калибровка не применялась.

На test: ROC-AUC **0.90522**, Average Precision **0.41241**, prevalence **0.05369**, Brier **0.03951**, log loss **0.14104**. Полный отчёт содержит confusion matrix на T_manual и распределения score; matrix считается на всём split, а review coverage — на пригодном validation-подмножестве. Все числа относятся к искусственной симуляции.

Bundle: `ml/artifacts/baseline/` — preprocessing+model, manifest с версиями библиотек/dataset+split+evaluation hashes, feature code digest, selection lock, policy, model card. Startup проверяет hashes и версии; ничего не скачивает и не обучает. Веса и датасет исключены из Git. Небольшие отчёты в `reports/` и synthetic fixtures можно передавать команде. Это исследовательская сборка; независимый peer review для командного релиза ещё нужен.

Выполнены 13 unit/API проверок: Decimal, баланс/знак/нулевой долг, batch-online parity, whitelist/manifest, приоритет policy и равенство порогу, cap/minimum, реальные concurrent retries, conflicts/digests/purpose/schema/auth и API schemas. Фактический протокол runtime — `reports/ml-runtime.json`; результаты S01–S06 и 30 последовательных замеров feature+inference — `reports/ml-scenarios.json`. Это latency standalone ML, не время банковского пути и не нагрузочное испытание нескольких клиентов.

При `up --offline` и PostgreSQL, и ML запускаются под системным macOS sandbox с разрешением loopback/Unix sockets и запретом внешней сети. Проверены настоящее внешнее TCP-блокирование, перезапуск с сохранением snapshot/inference, неизменность bundle и отказ результата при недоступной долговечной записи.

## 8. Что реализовать интегратору

- Финансовый источник/черновик, provenance, полномочия, согласие и явное подтверждение восьми значений.
- Immutable финансовые/пакетные snapshots и reference, доступную к моменту submit.
- Вызовы Feature → Risk с общим бюджетом и закреплёнными версиями; долговечные operation/outbox/inbox.
- Policy по заданному приоритету; публичное объяснение без score/internalReasonCodes.
- RFI correction/explanation, amendment, попытки и защита от запоздавшего inference.
- Оферты, CAS принятия/expiry/cancel, отдельные операторские права и демонстрационное завершение.
- UI финансовой формы, статуса, RFI и предложений. В UI нет порога и пересчёта банковского решения.

OCR, RAG, ranking, внешние ФНС/БКИ/банковские сервисы не реализованы в этом ML-срезе. Их существующие контракты сохранены.
