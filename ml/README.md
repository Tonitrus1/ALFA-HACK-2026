# ML

Папка для самостоятельных ML-компонентов и экспериментов.

- [OCR → LLM → Structured JSON](ocr/README.md): независимый CPU-сервис, Docker Compose,
  типизированная JSON Schema, постоянные задания и TTL 24 часа. Подключение к
  общему backend/frontend выполняется отдельной интеграцией.

- [Руководство ML](../docs/architecture/packages/ml/docs/guide.md).
- [Руководство в PDF](../docs/architecture/packages/ml/ml-guide.pdf).
- [Внутренний API](../docs/architecture/contracts/internal.openapi.json) и [схемы событий ML](../docs/architecture/contracts/ml-events-v1.schema.json).
- [Правила работы команды](../CONTRIBUTING.md).

Создавайте ветку под задачу от свежей `main`, например `ml/scoring`, и открывайте Pull Request в `main`. Датасеты, веса моделей и кеши храните вне Git; для воспроизводимости фиксируйте версии и контрольные суммы по архитектурному регламенту.
