# Бэкенд

Серверный код, бизнес-логика и миграции. Сейчас здесь каркас без бизнес-логики: модули, порты, выбор провайдеров, схемы БД и архитектурные тесты.

- [Руководство бэкенда](../docs/architecture/packages/backend/docs/guide.md).
- [Руководство в PDF](../docs/architecture/packages/backend/backend-guide.pdf).
- [Публичный API](../docs/architecture/contracts/public.openapi.json) и [внутренний API](../docs/architecture/contracts/internal.openapi.json).
- [Правила работы команды](../CONTRIBUTING.md).

Создавайте ветку под задачу от свежей `main`, например `backend/applications`, и открывайте Pull Request в `main`.

## Стек

Java 21, Spring Boot 4.1.1, PostgreSQL 17.11, Maven (через `./mvnw`), Flyway, ArchUnit, Testcontainers. Это документальные ориентиры; точные версии и digests закрывает P02.

## Структура

| Путь | Что внутри |
| --- | --- |
| `ports/` | Порты способностей: `SessionStorePort`, `CachePort`, `EventTransportPort`, `ObjectStorePort`, классы ошибок. Без Spring и SDK |
| `adapters/local/` | Локальные адаптеры профиля `local-mvp` (P25) |
| `adapters/{redis,kafka,s3}/` | Отключённые каркасы настоящих провайдеров: выбор бросает `ProviderNotImplemented` |
| `app/` | Spring Boot приложение |
| `app/.../credit/<module>/` | Модули `access`, `catalog`, `applications`, `consents`, `documents`, `journey`, `integration`, `workspace`, `ml`, `kb`; слои `api` → `application` → `domain`, `infrastructure` |
| `app/.../credit/platform/bindings/` | Composition root: проверка `credit.adapters.*`; неизвестная привязка останавливает запуск |
| `app/src/main/resources/db/migration/<module>/` | Flyway-миграции модуля-владельца; номера версий глобальные |

Правила границ проверяет `ModuleBoundariesTest` (ArchUnit): другой модуль доступен только через его `application`, контроллеры не ходят в `infrastructure`, бизнес-модули не зависят от адаптеров.

## Запуск

Нужен JDK 21; Maven скачает `./mvnw`.

```bash
cd backend
./mvnw verify                      # сборка и тесты; тест с PostgreSQL пропускается без Docker

cp .env.example .env               # задать DB_PASSWORD
docker compose up -d               # локальный PostgreSQL 17.11
set -a; . ./.env; set +a
./mvnw install -DskipTests && ./mvnw -pl app spring-boot:run
```
