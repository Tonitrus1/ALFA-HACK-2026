# Каталог ML-сервисов

Текущее расширение скоринга: [две модели и политика шести сценариев](../docs/ml/scoring/dual-model.md).

Актуальность: 22.10.2026. Навигация по отдельным сервисам проекта. Эта ветка — `ml/local-scoring-runtime`, исходный снимок `f14d090a956d2a9063da57a53c269237b5df6298`; каталог не означает объединение реализаций.

| Сервис | Ветка | Точка входа | Наличие |
|---|---|---|---|
| Скоринг | [ml/local-scoring-runtime](https://github.com/Tonitrus1/ALFA-HACK-2026/tree/ml/local-scoring-runtime) | [README](scoring/README.md) | В этой ветке |
| Рекомендации | [ml/feed-recommendations](https://github.com/Tonitrus1/ALFA-HACK-2026/tree/ml/feed-recommendations) | [Перейти в ветку](https://github.com/Tonitrus1/ALFA-HACK-2026/tree/ml/feed-recommendations) | Отдельная поставка; здесь отсутствует |
| Ассистент | [assistant-service](https://github.com/Tonitrus1/ALFA-HACK-2026/tree/assistant-service) | [Перейти в ветку](https://github.com/Tonitrus1/ALFA-HACK-2026/tree/assistant-service) | Отдельная поставка; здесь отсутствует |

## Документация и правила

[Единый каталог документации](../docs/ml/README.md). В каждой ветке локально документируется её собственный сервис; ссылки на остальные ведут в соответствующие GitHub-ветки. У моделей раздельные зависимости, веса, запуск и состояние. Ветка assistant-service не изменялась этой миграцией.
