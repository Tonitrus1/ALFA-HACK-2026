# Бэкенд

Серверный код, бизнес-логика и миграции. Сейчас здесь каркас без бизнес-логики: модули, порты, выбор провайдеров, схемы БД и архитектурные тесты.

- [Руководство бэкенда](../docs/architecture/packages/backend/docs/guide.md).
- [Руководство в PDF](../docs/architecture/packages/backend/backend-guide.pdf).
- [Публичный API](../docs/architecture/contracts/public.openapi.json) и [внутренний API](../docs/architecture/contracts/internal.openapi.json).
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
- Предусловия submit — `SubmissionPrerequisites`: финансы (P08) проверяются по-настоящему; непустые ссылки на документы/согласия отклоняются до P10/модуля согласий (`DocumentReferenceGate`).
- Синтетический каталог (`working-capital`, `credit-line`, `overdraft`) — в seed профиля `demo`.

## Финансовая анкета (P08)

- `GET/PUT /api/v1/applications/{id}/financial-statement`, `POST .../confirm`; `If-Match` — ETag заявки (`containerVersion`), не `statementVersion`.
- PUT заменяет форму DEMO Financial v1 (один календарный год, RUB, копейки; неполный черновик разрешён). Изменение содержимого → новая `statementVersion`, подтверждение сброшено. Тот же ввод ничего не меняет.
- Confirm: все 8 полей, `totalAssets > 0`, `currentAssets ≤ totalAssets`, `currentLiabilities ≤ totalLiabilities`, баланс с demo-допуском `max(100 коп., 1% totalAssets)`, точные `documentReferences`. Provenance (MANUAL, actor, time) формирует сервер; клиент не может прислать `confirmed`/provenance.
- Submit закрепляет неизменяемый `financial_snapshot` подтверждённой версии в той же транзакции; `financialSnapshotId` создаёт сервер.

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
