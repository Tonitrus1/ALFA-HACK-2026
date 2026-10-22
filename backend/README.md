# Бэкенд

> **Интеграционная поставка 22.10.2026:** backend + реальные Risk/Feed, ML bridge и Compose. Текущая архитектура, запуск и ограничения: [руководство интеграции](../docs/integration-mvp.md). Исторические описания ниже относятся к исходным веткам и не подтверждают этот runtime.


Серверный код, бизнес-логика и миграции. Сейчас здесь каркас без бизнес-логики: модули, порты, выбор провайдеров, схемы БД и архитектурные тесты.

- [Руководство бэкенда](../docs/architecture/packages/backend/docs/guide.md).
- [Руководство в PDF](../docs/architecture/packages/backend/backend-guide.pdf).
- [Публичный API](../docs/architecture/contracts/public.openapi.json) и [внутренний API](../docs/architecture/contracts/internal.openapi.json).
- [Интеграция рекомендательной ленты](../docs/feed-integration.md): вызов E5, fallback, профили, реакции, cursor и хранение.
- [Клиент-пример](../ml/feed/integration.py) и [образец семантики реакций](../ml/feed/backend_reference.py).
- [Правила работы команды](../CONTRIBUTING.md).

Создавайте ветку под задачу от свежей `main`, например `backend/applications`, и открывайте Pull Request в `main`.

## Стек

Java 21, Spring Boot 4.1.1, PostgreSQL 17.11, Maven (через `./mvnw`), Flyway, ArchUnit, embedded-postgres для тестов. Это документальные ориентиры; точные версии и digests закрывает P02.

## Структура

| Путь | Что внутри |
| --- | --- |
| `ports/` | Порты способностей: `SessionStorePort`, `CachePort`, `EventTransportPort`, `ObjectStorePort`, классы ошибок. Без Spring и SDK |
| `adapters/local/` | Локальные адаптеры профиля `local-mvp`: `JdbcSessionAdapter`, `BoundedLocalCacheAdapter`, `PostgresOutboxTransportAdapter`, `VersionedFilesystemObjectAdapter` |
| `adapters/{redis,kafka,s3}/` | Отключённые каркасы настоящих провайдеров: выбор бросает `ProviderNotImplemented` |
| `app/` | Spring Boot приложение |
| `app/.../credit/<module>/` | Модули `access`, `catalog`, `applications`, `consents`, `documents`, `journey`, `integration`, `workspace`, `ml`, `kb`; слои `api` → `application` → `domain`, `infrastructure` |
| `app/.../credit/platform/bindings/` | Composition root: по `credit.adapters.*` создаёт ровно одну реализацию каждого порта; неизвестная или неподключённая привязка останавливает запуск, автоматического fallback нет |
| `app/src/main/resources/db/migration/<module>/` | Flyway-миграции модуля-владельца; номера версий глобальные |

Правила границ проверяет `ModuleBoundariesTest` (ArchUnit): другой модуль доступен только через его `application`, контроллеры не ходят в `infrastructure`, бизнес-модули не зависят от адаптеров.

## Доступ и сессии (P03)

- Сессия — cookie `credit_session` (HttpOnly, SameSite=Strict); в БД хранится только SHA-256 токена (`access.session`).
- Все `/api/v1/**` требуют сессию (401). Изменяющие методы требуют `X-CSRF-Token` (403). `X-Company-Context` сверяется с `contextVersion` до эффекта (409 `COMPANY_CONTEXT_CHANGED`).
- Чужая компания неотличима от несуществующей (404). Для ресурсов компании другие модули используют `CompanyAccessService.requireSelectedCompany` / `requireAction`, а сессию получают параметром контроллера `AuthenticatedSession`.
- Повышение `access.actor.auth_epoch` мгновенно отзывает все сессии участника.
- Demo-вход (`/demo/api/v1/accounts`, `/demo/api/v1/session`) существует только в профиле `demo`; там же Flyway подключает синтетический seed `db/seed/demo`: `representative-a` → `company-a`, `representative-b` → `company-b`, `operator-demo`.

## Заявки, команды и симулятор (P05)

- `GET /api/v1/products`; `POST/GET /api/v1/applications`, `GET/PATCH /api/v1/applications/{id}`, `POST .../submit`, `GET .../status`, `GET /api/v1/operations/{id}`.
- Create — 201 с повтором по `Idempotency-Key` (тот же ресурс; другой body — 409 `IDEMPOTENCY_KEY_REUSED`). PATCH — `If-Match: "v{n}"`, CAS по версии.
- Submit — 202 + receipt. Повтор с тем же ключом возвращает исходный receipt до проверок состояния. Один commit: заявка → `SUBMITTED`, неизменяемый `submission_snapshot`, `command_operation`, событие `SubmissionRequested` в `journey.outbox`.
- `OutboxDispatcher` (SKIP LOCKED, lease, backoff, видимый `FAILED`) доставляет события в in-process обработчики. `BankSimulator` по inbox создаёт дело (дедуп по `externalRequestId`), переводит операцию в `SUCCEEDED` и публикует `CaseAccepted` (статус `REVIEW`).
- Предусловия submit — `SubmissionPrerequisites`: финансы (P08) и точные CLEAN-ссылки на документы (P10) проверяются по-настоящему; непустой список согласий отклоняется до модуля согласий.
- Синтетический каталог (`working-capital`, `credit-line`, `overdraft`) — в seed профиля `demo`.

## Финансовая анкета (P08)

- `GET/PUT /api/v1/applications/{id}/financial-statement`, `POST .../confirm`; `If-Match` — ETag заявки (`containerVersion`), не `statementVersion`.
- PUT заменяет форму DEMO Financial v1 (один календарный год, RUB, копейки; неполный черновик разрешён). Изменение содержимого → новая `statementVersion`, подтверждение сброшено. Тот же ввод ничего не меняет.
- Confirm: все 8 полей, `totalAssets > 0`, `currentAssets ≤ totalAssets`, `currentLiabilities ≤ totalLiabilities`, баланс с demo-допуском `max(100 коп., 1% totalAssets)`, точные `documentReferences`. Provenance (MANUAL, actor, time) формирует сервер; клиент не может прислать `confirmed`/provenance.
- Submit закрепляет неизменяемый `financial_snapshot` подтверждённой версии в той же транзакции; `financialSnapshotId` создаёт сервер.

## Документы и сканер (P10)

- `GET .../document-requirements`, `POST .../documents/upload-intents` (201, грант 10 мин, связан с сессией), `PUT /api/v1/files/uploads/{transferId}` с `X-Upload-Grant` (поток в карантин, 204), `DELETE /api/v1/uploads/{id}`, `GET .../documents`, `GET /api/v1/documents/{id}`, `POST .../download-intents` + `GET /api/v1/files/downloads/{transferId}` с `X-Download-Grant` (только точная CLEAN-версия), `GET .../extraction`.
- Финализация и отмена загрузки — один CAS upload-state; размер сверяется с объявленным, лимит 10 MiB.
- In-process сканер (роль `file-scanner`) берёт SCAN-задание с арендой: сигнатура и структура (`FileInspector`: ≤ 5 страниц PDF, без шифрования/JavaScript/вложений, ≤ 40 млн пикселей, полиглоты отклоняются), затем ClamAV `clamd` (`CLAMD_HOST`/`CLAMD_PORT`). CLEAN — только по положительному вердикту; INFECTED → REJECTED; ERROR оставляет карантин, после 5 попыток задание `FAILED`. Выключается `credit.scanner.enabled=false`, если сканер будет внешним.
- Внутренний API `/internal/v1/document-jobs/{claim,renew,scan-result,extraction-result}` для OCR-worker ML: заголовок `X-Service-Token` (`FILE_SCANNER_TOKEN`, `DOCUMENT_OCR_TOKEN`, ≥ 32 символов). Результат принимается только от текущего поколения непросроченной аренды для той же `objectVersion` (иначе 409 `LEASE_STALE`).
- Не сделано в P10: `confirm-extraction` (перенос OCR-значений в анкету с OCR-provenance), загрузки по RFI (P15), внешний file-gateway (`/internal/v1/uploads/*/complete`, `/transfers/*/authorize`) — шлюз встроен в backend; сборка осиротевших карантинных байтов.

## ML-адаптеры, решения и RFI (P15)

- `ml`: `RiskGateway` (feature snapshot → risk evaluation по точному финансовому снимку; ответ сверяется по snapshot/digest/score/calibration, запись в `ml.inference_record` до использования), `RankingGateway` (только полная перестановка кандидатов, иначе RULES в порядке backend), `AssistantGateway` (цитаты только из allowlist и текущего `kbEpoch`, иначе INSUFFICIENT_EVIDENCE).
- Транспорт ML: `credit.ml.mode` = `contract-double` (по умолчанию, детерминированный двойник по схемам internal v2 — **не модель**, помечается `CONTRACT_DOUBLE`) или `http` (`ML_BASE_URL`, `ML_SERVICE_TOKEN`, бюджеты 2/3/60 с). Неизвестный режим останавливает запуск.
- Симулятор: после `CaseAccepted` дело встаёт в `integration.review_task`; `ReviewWorker` вызывает риск вне транзакции и одним commit (CAS по `caseVersion`) записывает решение `demo-policy-v1`, предложение (+24 ч) и события. Сбой риска → MANUAL, без автоматического отказа.
- `GET /api/v1/applications/{id}/decision` (MANUAL ещё не решение — 404 `DECISION_NOT_READY`), `GET /api/v1/offers/{id}`.
- Финансовый RFI: противоречие выручки в анкете и отчётности (> 50%) → NEEDS_INFO с FIELD `financialStatement.values.revenueMinor`. Черновик ответа — копия подтверждённой формы; менять можно только запрошенные значения (иначе 422 `FIELD_NOT_REQUESTED`); ответ (202, RESPOND) создаёт новый неизменяемый снимок; банк возвращает дело в REVIEW и рассматривает по новому снимку. Исходная анкета не меняется.
- Не сделано: принятие предложения, отзыв заявки, операторские действия demo, публичные эндпоинты ленты/рекомендаций/ассистента (P12/P14/P16 используют готовые шлюзы).

## Запуск

Нужен JDK 21; Maven скачает `./mvnw`.

```bash
cd backend
./mvnw verify                      # сборка и тесты; встроенный PostgreSQL 17.11, Docker не нужен

cp .env.example .env               # задать DB_PASSWORD; файлы — в OBJECTS_ROOT (по умолчанию ~/.local/share/credit-backend/objects)
docker compose up -d               # локальный PostgreSQL 17.11
set -a; . ./.env; set +a
./mvnw install -DskipTests && ./mvnw -pl app spring-boot:run -Dspring-boot.run.profiles=demo
```
