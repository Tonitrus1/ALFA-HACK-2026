# Кредитный кабинет предпринимателя — приложение

ШАБЛОН БУДУЩЕГО РЕПОЗИТОРИЯ. Заполняется фактическими результатами P20/P21. Сейчас приложение не поставляется.

## Назначение и границы

Synthetic web credit journey; simulated bank integrations; no real lending. Указать реализованные и незавершённые функции, архитектурную схему и выбранную версию API.

## Требования и запуск

Указать измеренные OS/CPU/ISA/RAM/disk, Docker/Compose, время startup/warmup, exact model bundle и бесплатный способ подготовки/offline load с SHA-256. Основная команда будущего запуска: docker compose -f deploy/compose.yaml up --build -d. Перечислить healthchecks, URL/порты, переменные из .env.example, действия при failed readiness.

## Проверка

Дать synthetic company A/B accounts и отдельный demo-operator; happy path, RFI, OCR confirm, semantic feed, real risk, RAG source; restart, чужая компания и model failure. Указать точные ожидаемые результаты и reset demo data без удаления пользовательских данных. Приложить OpenAPI, коллекцию запросов, state/data diagrams и сценарии приёмки.

## Поставка

Commit SHA/tag до дедлайна, время/timezone, images/model digests, THIRD_PARTY_NOTICES, фактический clean-start протокол, ограничения proxy и целевой план развития. Не отмечать NOT_EXECUTED проверки выполненными.

## Технологический стек и фактические провайдеры

Приложить contracts/technology-adapters.json, выбранный binding profile и заполненный provider-evidence отчёт. Указать Qdrant/Redis/Feast и остальные компоненты: LOCAL_SUBSTITUTE, REAL_CONNECTED, TEST_DOUBLE или ARCHITECTURAL_SLOT. Для REAL_CONNECTED приложить реальный протокол с digest; каркас/контейнер без работающего вызова не считается интеграцией. Описать включение дополнительных сервисов, их версии, ресурсы и способ вернуться к проверенному локальному профилю.
