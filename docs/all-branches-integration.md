# Интеграция всех веток, 25 октября 2026

Рабочий каталог: `integrated-mvp`. Ветка: `integration/all-branches-compose-20261025`. Основа — `integration/ui-feed-antifraud-mvp` (8e1a8e0): в ней уже согласованы реальные backend/Risk/Feed DTO, финансы, идемпотентность, UI и версия данных. Удалённые refs обновлены перед началом; [точный снимок SHA](integration-branch-heads.txt).

## Что взято из каждой ветки

| Ветка (SHA на начало) | Итог |
|---|---|
| main (f3621df) | Архитектура, контракты, правила совместной работы. Поставляется как документация; не подменяет runtime-проверки |
| backend/p03-data-session (b917220) | Flyway, PostgreSQL sessions, CSRF, company/tenant isolation, demo accounts |
| backend/p05-vertical-slice (e5f7ab6) | Создание/сохранение/подача заявки, outbox, операции и состояние рассмотрения |
| backend/p08-financial-form (7de3554) | Восемь финансовых значений, подтверждение, immutable snapshots и версии |
| backend/p10-documents (0676e3f) | Потоковая загрузка, quarantine, ClamAV, job leases. Добавлен защищённый download точной CLEAN-версии для OCR |
| backend/p15-ml-rfi-decisions (4f229b0) | ML gateways, решения, финансовый RFI, оферты; после интеграции вызывается реальный ML bridge |
| backend/p25-local-adapters (d774815) | Composition root, JDBC sessions, PostgreSQL outbox, bounded cache, filesystem objects. Kafka/Redis/S3 adapters сохранены; отдельные дублирующие сервисы не запускаются |
| ml/local-scoring-runtime (802f998) | CatBoost Risk baseline, synthetic antifraud bundle/API/features. Дополнительно перенесены генератор/обучение fraud, dual-policy reference и decision client. Основная Java-policy интеграции остаётся авторитетной |
| ml/feed-recommendations (87af049) | E5 v1 и расширенный E5/CatBoost pipeline. Новая реализация сохранена в `ml/feed_v2` с адаптированным namespace; один сервис `feed` выбирает релиз. Исторические v1 artifacts представлены существующим `ml/feed/release`, не запускаются как отдельный сервис |
| integration/ml-audit-20261021 (af86831) | Проверяемые model manifests/hashes, candidate evaluation/replay, неизменяемый baseline, ограничения синтетической оценки |
| integration/backend-ml-mvp (5b937b5) | Реальные HTTP backend→bridge→Risk/Feed, ML DB, durable idempotency, cursor/exposure/feedback, isolated Docker network и healthchecks |
| integration/ui-feed-antifraud-mvp (8e1a8e0) | Реальный UI/API adapter, финансовые суммы, применение RFI/offer commands, FeedPanel, версии Feed, synthetic reference и rollback compatibility |
| frontend/docker-package (a9cfed0) | Уже перенесённый кабинет, отдельные Dockerfile/nginx/Compose и инструкции. Сохранены бизнес-экраны; mock provisional API не вернулся в интеграционную сборку. Общий gateway сохраняет реальный API и DNS reload |
| ml/ocr-service (e7e0d09) | Весь standalone OCR, schema, prompts, lifecycle, tests, Tesseract/Paddle. Общий CPU Docker по умолчанию Tesseract; worker связывает backend leases с реальными OCR jobs и сохраняет соответствие в SQLite |
| assistant-service (ec10111) | Весь RAG/agent, E5, BM25/RRF, Qdrant, SearXNG, safe page reader, confirmed knowledge ingestion, admin API и тесты. Backend выдаёт trusted identity/context и хранит remote tokens; UI получил рабочий chat adapter |

Backend p03–p25 уже входят в ancestry основы. OCR и assistant включены отдельными merge-коммитами с сохранением документации ML. Frontend/Feed/scoring перенесены выборочно: слепое слияние заменило бы рабочие интеграционные API более старыми standalone-контрактами. [Файловая сверка источников](../reports/all-branches/source-inventory.json) отделяет одинаковые файлы от адаптированных.

## Сохранность рабочей копии

Корень `Alfa_hack` не является Git repo; в нём шесть копий одного репозитория. Изменения найдены только в `credit-workspace` (134 файла). До работы сохранены полный бинарный patch, исходные изменённые/untracked файлы и SHA всех копий в `../output/all-branches-integration-20261025/`. Исходная dirty-копия оставлена без изменений. Проверено: отсутствующих относительно неё файлов в интеграции нет; отличающиеся runtime-файлы — последующее развитие с backend profile/bridge/fraud и подтверждены регрессионными тестами. Локальные файлы окружения и модели из `.local` не опубликованы.

Исходные ветки не удалены, force push не использовался, production не изменялся.

## Согласование контрактов

- Авторизация и компании: browser cookie/CSRF остаются у backend; assistant identity задаётся только с отдельным service token. По одному имени диалога нельзя получить историю другой компании или другой browser session. На каждый ход передаётся read-only snapshot продуктов и заявок, прочитанный через авторизованные application services; модель не выполняет изменения заявок.
- OCR: роль `document-ocr`, отдельный токен, текущая аренда/поколение, CLEAN и точная objectVersion проверяются до чтения; аренда продлевается во время обработки. Просроченное поколение не публикует результат. Worker journal и OCR queue переживают рестарт. После аварии submit→journal возможен повтор платного вызова, но не запись в другую версию документа.
- OCR schema финансов: только extracted, RUB, с источником/страницей; отсутствующие/конфликтующие значения пропускаются. `total_debt` не равен `totalLiabilities`, автоматического преобразования нет. Подтверждение в UI повторно проверяет extractionId/objectVersion и financial version, затем сохраняет обычный подтверждённый statement.
- Risk/Feed: сохранены backend-specific digest/input profiles, PostgreSQL журналы и fallback semantics. Risk inference остаётся в Risk; bridge не пересчитывает модель.
- Удалённый LLM: общий endpoint/key, отдельные model names для assistant/OCR. Без ключа readiness честно возвращает 503; ответа-заглушки нет.

## Фактические проверки

Локальные результаты после интеграции:

- frontend TypeScript + Vite production build — PASS;
- frontend 46 unit-тестов — PASS; старые mock-тесты приведены к действующим статусам APPROVED/NEEDS_INFO/REVIEW;
- OCR 36 unit/contract/adapter тестов — PASS, без утверждения о вызове модели;
- assistant 65 unit/contract тестов — PASS, 2 требующих внешнего Qdrant/E5 пропущены; после дополнительных проверок авторизации число обновляется итоговым CI;
- Java Maven verify с реальным embedded PostgreSQL — PASS, 132 теста, 4 прежних skipped; добавлена отдельная проверка backend↔assistant adapter isolation;
- Linux чистая Docker-сборка и smoke — текущие результаты GitHub Actions и загружаемый artifact `integrated-linux-evidence`; итоговый статус будет записан после завершения.

На локальном macOS Docker Engine отсутствует. Это не подменено native-проверкой: контейнерная приёмка запускается на Linux GitHub Actions. Workflow проверяет реальные модели E5/CatBoost, UI→backend→ML→DB, ClamAV, file download/tenant isolation, failures и restart/recreate с теми же volumes. Все сервисы AI собираются/стартуют отдельно, actual Tesseract проверяется на синтетическом изображении. В CI ключ LLM не предоставлен: генерация assistant и OCR→LLM extraction остаются **BLOCKED_LLM_API_KEY_MISSING**, в отчётах readiness это явно отделено от локального RAG/OCR engine.

Команда запуска и настройки: [README](../README.md). Результаты синтетических моделей не являются банковской PD, antifraud-вердиктом или подтверждением кредитного качества.
