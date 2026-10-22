## UI / Feed v2 / synthetic proxy

Новый интеграционный срез и приёмка: [руководство](docs/ui-feed-antifraud-runbook.md), [решения по контрактам](docs/ui-feed-antifraud-decisions.md). Исходный E5 v1 сохранён; CatBoost Feed включается только явно. Чат/OCR запланированы отдельно.

# Кредитный кабинет предпринимателя

> **Интеграционная поставка 22.10.2026:** backend + реальные Risk/Feed, ML bridge и Compose. Текущая архитектура, запуск и ограничения: [docs/integration-mvp.md](docs/integration-mvp.md). Исторические описания ниже относятся к исходным веткам и не подтверждают этот runtime.


Совместный проект команды из пяти человек для Alfa Hack 2026.

Реализован **локальный ML-срез скоринга**: рабочий CatBoost baseline, обучение новых кандидатов логрега/CatBoost с вложенной оценкой, Risk API, PostgreSQL snapshots/inference, S01–S06 и документация интеграции. Новые кандидаты сохраняют контракт восьми финансовых полей и не заменяют рабочую модель автоматически. UI и backend-процесс заявки реализуют другие участники. Полный объём HACKATHON-1.5 остаётся спецификацией.

Запуск подготовленного ML: `./scripts/demo up --offline`; сценарии: `./scripts/demo scenarios`. Первичная подготовка, обучение, API и границы ответственности: [передача ML-модуля](docs/ml-integration.md).

Реализована также **ML-лента о финансировании бизнеса**: локальная E5 на CPU, 36 карточек, шесть SVG, внутренний API на 8002 и резервный подбор. Подготовка: `./scripts/feed setup`, `./scripts/feed prepare --download`; [запуск и интеграция ленты](docs/feed-integration.md), [модуль](ml/feed/README.md).

## Направления разработки

| Направление | Папка | Руководство | PDF |
| --- | --- | --- | --- |
| Фронтенд | [frontend/](frontend/README.md) | [Архитектура и задачи](docs/architecture/packages/frontend/docs/guide.md) | [Скачать](docs/architecture/packages/frontend/frontend-guide.pdf) |
| Бэкенд | [backend/](backend/README.md) | [Архитектура и задачи](docs/architecture/packages/backend/docs/guide.md) | [Скачать](docs/architecture/packages/backend/backend-guide.pdf) |
| ML | [ml/](ml/README.md) | [Архитектура и задачи](docs/architecture/packages/ml/docs/guide.md) | [Скачать](docs/architecture/packages/ml/ml-guide.pdf) |

## Документация

- [Передача объединённых ML-модулей команде: ветки, контракты, запуск и ограничения](docs/ml-team-handoff.md).
- [Аудит ML, исправления и дальнейший план качества](docs/ml-audit-20261021.md).
- [Оглавление архитектуры HACKATHON-1.5](docs/architecture/README.md).
- [Общая архитектура](docs/architecture/packages/general/docs/guide.md) и [PDF](docs/architecture/packages/general/general-guide.pdf).
- [План разработки](docs/architecture/docs/development-plan.md).
- [Атлас схем](docs/architecture/architecture-atlas.pdf), [редактируемая схема draw.io](docs/architecture/architecture.drawio) и [SVG-схемы](docs/architecture/diagrams/).
- [Аудит архитектуры](docs/architecture/docs/architecture-audit.md).
- [Технологии и адаптеры](docs/architecture/docs/technology-adapters.md).
- [Публичный OpenAPI](docs/architecture/contracts/public.openapi.json), [внутренний OpenAPI](docs/architecture/contracts/internal.openapi.json) и [коллекция Postman](docs/architecture/contracts/requests.postman_collection.json).
- [Критерии приёмки](docs/architecture/docs/acceptance.md).
- [Исходный регламент работы с Git и защиты проекта](docs/architecture/docs/git-and-jury-guide.md).

Актуальные редактируемые контракты находятся в `docs/architecture/contracts/`. API-копии внутри пакетов направлений генерируются: не редактируйте их независимо. Упоминания корневых папок приложения в архитектурном комплекте описывают будущую структуру приложения.

Полный архитектурный комплект сохранён в `docs/architecture/` с исходной структурой, генераторами, лицензиями, контрольными суммами и архивом исторических материалов. Исходные документы находятся в `docs/architecture/evidence/originals.zip`. Отчёты PASS этого комплекта относятся к статической спецификации, а не к работающему приложению.

HTML-обзор `docs/architecture/index.html` можно открыть локально после скачивания репозитория. Для чтения непосредственно на GitHub используйте Markdown и PDF по ссылкам выше.

## Совместная работа

Начните с [CONTRIBUTING.md](CONTRIBUTING.md). Общая ветка — `main`; для каждой задачи создаётся отдельная ветка: `frontend/login`, `backend/applications`, `ml/scoring` или `docs/setup`. Изменения проходят Pull Request и проверку другого участника.

Владелец репозитория — **@Tonitrus1**. Четыре коллеги будут приглашены после получения их GitHub-логинов; владельцы направлений пока не назначены. Постоянные ветки направлений не используются.

При настройке этого приватного репозитория GitHub сообщил, что автоматическая защита `main` требует GitHub Pro. Поэтому пока правила проверки изменений из CONTRIBUTING.md соблюдаются командой по договорённости. Приватность сохранена, платный тариф не подключался.
