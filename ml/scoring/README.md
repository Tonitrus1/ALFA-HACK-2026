# Кредитный скоринг

Принимает подтверждённую финансовую отчётность, создаёт неизменяемые признаки и возвращает долговечно сохранённый риск-score для backend. Решение и оферта принадлежат backend policy.

| Параметр | Значение |
|---|---|
| Статус | Локальный ML реализован; общий backend/frontend и совместная приёмка не поставлены |
| Актуальность | 22.10.2026; `ml/local-scoring-runtime`; код `f14d090a956d2a9063da57a53c269237b5df6298` |
| Проверенная среда | Исторические протоколы: macOS arm64, Python 3.12.13; Docker/Windows/Linux не проверены |
| Адрес сервиса | 127.0.0.1:8001 |
| Модели | catboost-optuna-v1; кандидат в этом снимке отсутствует |
| Зависимости runtime | PostgreSQL 17.5 и файловый bundle |

## Назначение и границы

BANKRUPTCY_PROXY/DEMONSTRATION/DEMO_RESEARCH на синтетике; не банковская PD. Application lifecycle и банковская policy отдельно. Фактические проверки и непройденные сценарии отдельно перечислены в verification.

## Быстрый запуск

Сначала [первичная подготовка](../../docs/ml/scoring/setup.md). Ниже обычный запуск в уже подготовленном окружении; конфигурацию создаёт launcher.

ОС/оболочка: macOS arm64, POSIX shell. Рабочий каталог: корень соответствующей ветки репозитория.

```sh
./scripts/demo up --offline
```

Ожидается сервис на указанном порту. При запуске не происходит переобучения или скачивания модели.

## Проверка запуска

Авторизованный `GET http://127.0.0.1:8001/health`: Bearer; ожидается HTTP200 и ready=true. Без токена 403. Исполняемая команда — в setup.

## Документация

- Подготовка и настройки — [setup.md](../../docs/ml/scoring/setup.md).
- Архитектура — [architecture.md](../../docs/ml/scoring/architecture.md).
- API и интеграция — [integration.md](../../docs/ml/scoring/integration.md).
- Модели и качество — [model-card.md](../../docs/ml/scoring/model-card.md).
- Данные и происхождение — [data.md](../../docs/ml/scoring/data.md).
- Обслуживание — [operations.md](../../docs/ml/scoring/operations.md).
- Фактические проверки — [verification.md](../../docs/ml/scoring/verification.md).
- Сторонние компоненты — [THIRD_PARTY_NOTICES.md](../../docs/ml/scoring/THIRD_PARTY_NOTICES.md).
- Изменения — [CHANGELOG.md](../../docs/ml/scoring/CHANGELOG.md).
