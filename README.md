# Кредитный кабинет предпринимателя

Единая документация ML: [каталог сервисов](ml/README.md) · [правила и навигация](docs/ml/README.md). Формат унифицирован 22.10.2026. Текущее расширение: [две модели и политика](docs/ml/scoring/dual-model.md).

Совместный проект команды из пяти человек для Alfa Hack 2026.

Реализован **локальный ML-срез скоринга**: неизменённый CatBoost кредитного риска, отдельный CatBoost манипуляций отчётностью, Risk/Fraud API, PostgreSQL snapshots/inference и политика S01–S06. Антифрод обучен на синтетике; обнаружение новых типов атак не подтверждено. UI и backend-процесс заявки реализуют другие участники. Полный объём HACKATHON-1.5 остаётся спецификацией.

Запуск подготовленного ML: `./scripts/demo up --offline`; сценарии: `./scripts/demo scenarios`. Первичная подготовка, обучение, API и границы ответственности: [передача ML-модуля](docs/ml-integration.md).

## Направления разработки

| Направление | Папка | Руководство | PDF |
| --- | --- | --- | --- |
| Фронтенд | [frontend/](frontend/README.md) | [Архитектура и задачи](docs/architecture/packages/frontend/docs/guide.md) | [Скачать](docs/architecture/packages/frontend/frontend-guide.pdf) |
| Бэкенд | [backend/](backend/README.md) | [Архитектура и задачи](docs/architecture/packages/backend/docs/guide.md) | [Скачать](docs/architecture/packages/backend/backend-guide.pdf) |
| ML | [ml/](ml/README.md) | [Архитектура и задачи](docs/architecture/packages/ml/docs/guide.md) | [Скачать](docs/architecture/packages/ml/ml-guide.pdf) |

## Документация

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
