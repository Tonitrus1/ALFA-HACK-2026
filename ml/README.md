# Каталог ML-сервисов

Актуальность: 22.10.2026. Навигация по отдельным сервисам проекта. Эта ветка — `ml/feed-recommendations`, исходный снимок `829c1c09bb248f03d730f25526de3b11712370bd`; каталог не означает объединение реализаций.

| Сервис | Ветка | Точка входа | Наличие |
|---|---|---|---|
| Скоринг | [ml/local-scoring-runtime](https://github.com/Tonitrus1/ALFA-HACK-2026/tree/ml/local-scoring-runtime) | [Перейти в ветку](https://github.com/Tonitrus1/ALFA-HACK-2026/tree/ml/local-scoring-runtime) | Отдельная поставка; здесь отсутствует |
| Рекомендации | [ml/feed-recommendations](https://github.com/Tonitrus1/ALFA-HACK-2026/tree/ml/feed-recommendations) | [README](feed/README.md) | В этой ветке |
| Ассистент | [assistant-service](https://github.com/Tonitrus1/ALFA-HACK-2026/tree/assistant-service) | [Перейти в ветку](https://github.com/Tonitrus1/ALFA-HACK-2026/tree/assistant-service) | Отдельная поставка; здесь отсутствует |

## Документация и правила

[Единый каталог документации](../docs/ml/README.md). В каждой ветке локально документируется её собственный сервис; ссылки на остальные ведут в соответствующие GitHub-ветки. У моделей раздельные зависимости, веса, запуск и состояние. Ветка assistant-service не изменялась этой миграцией.
