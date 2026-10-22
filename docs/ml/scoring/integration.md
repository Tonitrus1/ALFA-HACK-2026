# Интеграция скоринга с backend и frontend

Назначение: интеграция скоринга с backend и frontend.

Статус реализации: отдельный локальный ML-сервис; публичный backend и frontend не поставляются. Статус проверки документации — в [verification.md](verification.md).

Актуальность: 22.10.2026. Исходный проверяемый снимок: `ml/local-scoring-runtime` / [`f14d090a956d`](https://github.com/Tonitrus1/ALFA-HACK-2026/commit/f14d090a956d2a9063da57a53c269237b5df6298). Среда исторических runtime-проверок: macOS arm64, Python 3.12.13. При этой миграции сервисы повторно не запускались.

## Статус интеграции и ответственность сервисов

Модель считает непрерывный `score` от 0 до 1 по восьми отношениям финансовой отчётности. Алгоритм: `CatBoostClassifier` с подбором гиперпараметров через Optuna. Код преобразования общий для обучения и serving: `ml/scoring/features.py`.

Назначение результата строго `BANKRUPTCY_PROXY / DEMONSTRATION / DEMO_RESEARCH`. Компании, финансы и целевая переменная полностью вымышлены. Это не банковская PD, не оценка настоящих российских компаний и не обещание кредита.

Модель не возвращает APPROVED/DECLINED. Эти маршруты выбирает backend policy. Исполняемый эталон для переноса и проверки интеграции: `ml/scoring/demo_policy.py`; он не изменяет заявки и не выпускает оферты. Сценарный CLI объединяет настоящие ML-вызовы с этим эталоном, чтобы разработчик мог воспроизвести маршруты заранее.

## Адреса, авторизация и идентификаторы

Адрес ML — `http://127.0.0.1:8001`; PostgreSQL — отдельная локальная БД на 55432. Заголовок `Authorization: Bearer <ML_INTERNAL_TOKEN>`, включая health. Токен только между сервисами. Application/submission/financial IDs принадлежат backend, featureSnapshotId/inferenceId выдаёт ML. requestId не менять при retry одной попытки.

## Источники контрактов

- [Нормативный OpenAPI](../../architecture/contracts/internal.openapi.json).
- [Runtime OpenAPI этого снимка](../../../ml/openapi.json); живой FastAPI также предоставляет `/openapi.json`.
- [Реализованный локальный профиль](../../architecture/contracts/local-risk-profile.json).
- [Клиент-пример](../../../ml/scoring/client.py).

Это профиль `DEMO_RESEARCH`, feature schema 2 и результат `BANKRUPTCY_PROXY`, не универсальная реализация всех операций большой схемы. Подключение к банковскому CREDIT_RISK требует отдельно реализованного адаптера/валидации; менять purpose ради совместимости нельзя.

| Операция | Вход | Выход | Авторизация | Ошибки | Пример |
|---|---|---|---|---|---|
| POST /internal/v2/feature-snapshots | FinancialStatement и IDs/digest | Immutable FeatureSnapshot | Bearer | 403/409/422/503 | [запрос](../../../ml/examples/create-feature.request.json) |
| GET /internal/v2/feature-snapshots/{id} | Точный ID | Сохранённый snapshot | Bearer | 403/404/503 | [ответ](../../../ml/examples/feature-snapshot.response.json) |
| POST /internal/v2/risk/evaluations | requestId, snapshot/digest, bundleDigest | Долговечный inference + score | Bearer | 403/404/409/422/503 | [запрос](../../../ml/examples/risk.request.json), [ответ](../../../ml/examples/risk.response.json) |
| GET /internal/v2/bundle | Без тела | Manifest и policy | Bearer | 403/5xx | [manifest](../../../ml/artifacts/baseline/manifest.json) |
| GET /health | Без тела | ready и bundleDigest | Bearer | 403/5xx | [проверка](setup.md#проверка-готовности) |

## Последовательность вызовов

Каноническая спецификация: `docs/architecture/contracts/internal.openapi.json`. Ограничения реализованного ML-профиля перечислены в `local-risk-profile.json`. Точная runtime-схема запросов доступна в `/openapi.json`. Остальные операции большого HACKATHON-1.5 контракта остаются спецификацией.

1. Backend сохраняет подтверждённый неизменяемый финансовый снимок и пакет отправки. Передаёт точную копию финансового блока в **POST `/internal/v2/feature-snapshots`**.
2. ML проверяет финансовые значения, digest и временную доступность; сохраняет неизменяемый FeatureSnapshot. **GET `/internal/v2/feature-snapshots/{id}`** читает именно эту версию.
3. Backend вызывает **POST `/internal/v2/risk/evaluations`** с ID/digest снимка, схемой 2, закреплённым bundleDigest и requestId попытки.
4. ML возвращает результат только после commit inference record. Backend отдельно применяет policy к своим закреплённым данным и условиям заявки.
5. **GET `/internal/v2/bundle`** возвращает manifest и подготовленную policy с T_manual. Закреплять эти версии на попытку; изменение bundle требует перепроверки policy и fixtures.



Минимальный путь интегратора: сохранить подтверждённые финансы → создать feature snapshot → передать его точные ID/digest в risk → закрепить inference → применить backend policy. Показанный API сам оферту не создаёт.

## Запросы и ответы

Исполняемые JSON находятся в [examples](../../../ml/examples/). Сохранённые UUID в ответах — результаты исторического прогона; перед новым inference получите собственный snapshot. Не перепечатывайте их как актуальные IDs.

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

При нулевых обязательствах X4/X8 дают `null`. CatBoost получает NaN и обрабатывает их через `nan_mode=Min`; отдельные imputer и scaler не используются. Batch/online используют один feature-builder.

Digest: SHA-256 UTF-8 JSON, ключи объектов рекурсивно сортируются, без пробелов, `ensure_ascii=False`, без NaN/Infinity. Financial digest считается от точного `financialStatement`. Snapshot digest — от всех полей FeatureSnapshot кроме самого `snapshotDigest`; ID/версии/время входят в hash. Backend может хранить snapshotDigest, возвращённый ML, и передавать его без повторной сериализации вещественных коэффициентов.

Ответ включает IDs, digests, scoreKind/calibrationStatus/purpose, modelVersion/releaseId и internalReasonCodes. В исследовательском профиле releaseId не означает принятие банковского релиза. В UI не выводятся внутренний score и причины модели как решение банка.

## Ошибки, timeout, retry, идемпотентность и fallback



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

## Совместимость версий и digests

Закрепляйте model bundle и policy на попытку; FinancialStatement hash нельзя пересчитать от другого представления денежных значений. Feature digest берите из ответа ML. Возврат для заменённой попытки не должен обновлять текущее дело. Совместное изменение schema, builder или bundle требует проверки потребителей. [Версии и обновление](operations.md).

## Обязанности backend и frontend

- Финансовый источник/черновик, provenance, полномочия, согласие и явное подтверждение восьми значений.
- Immutable финансовые/пакетные snapshots и reference, доступную к моменту submit.
- Вызовы Feature → Risk с общим бюджетом и закреплёнными версиями; долговечные operation/outbox/inbox.
- Policy по заданному приоритету; публичное объяснение без score/internalReasonCodes.
- RFI correction/explanation, amendment, попытки и защита от запоздавшего inference.
- Оферты, CAS принятия/expiry/cancel, отдельные операторские права и демонстрационное завершение.
- UI финансовой формы, статуса, RFI и предложений. В UI нет порога и пересчёта банковского решения.

OCR, RAG, ranking, внешние ФНС/БКИ/банковские сервисы не реализованы в этом ML-срезе. Их существующие контракты сохранены.

## Сквозные сценарии приёмки

S01 APPROVED; S02 DECLINED по demo-rule до ML; S03 NEEDS_INFO → новый снимок/настоящий inference → APPROVED; S04 ALTERNATIVE при превышении cap; S05 MANUAL по высокому score; S06 MANUAL при техническом сбое без выдуманного inference. Входы — [fixtures](../../../ml/fixtures/scenarios.json), исторический [протокол](../../../reports/ml-scenarios.json). Это standalone ML + reference policy, не готовый frontend/backend процесс заявки. Совместная приёмка пользовательского пути не выполнена.
