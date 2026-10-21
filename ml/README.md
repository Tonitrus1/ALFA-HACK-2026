# Рекомендательная лента

В этой ветке размещён только модуль [feed/](feed/README.md): E5, каталог 36 карточек, отдельный внутренний сервис на порту 8002 и резервные правила ранжирования.

- [Интеграция для frontend/backend](../docs/feed-integration.md).
- [Примеры запросов и ответов](feed/examples/).
- [Контракт сервиса](feed/openapi.json).
- Зависимости: `feed/requirements.lock.txt`; среда: `.venv-feed`; запуск: `./scripts/feed serve`.

Код, веса, зависимости и датасеты рисковика находятся в отдельной [ветке ml/local-scoring-runtime](https://github.com/Tonitrus1/ALFA-HACK-2026/tree/ml/local-scoring-runtime) и не включены сюда. Общие архитектурные материалы ниже описывают границы всего проекта.

- [Руководство ML](../docs/architecture/packages/ml/docs/guide.md).
- [Руководство в PDF](../docs/architecture/packages/ml/ml-guide.pdf).
- [Внутренний API](../docs/architecture/contracts/internal.openapi.json) и [схемы событий ML](../docs/architecture/contracts/ml-events-v1.schema.json).
- [Правила работы команды](../CONTRIBUTING.md).

Создавайте ветку под задачу от свежей `main`, например `ml/scoring`, и открывайте Pull Request в `main`. Датасеты, веса моделей и кеши храните вне Git; для воспроизводимости фиксируйте версии и контрольные суммы по архитектурному регламенту.
