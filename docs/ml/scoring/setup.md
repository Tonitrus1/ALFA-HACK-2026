# Подготовка и настройки скоринга

Актуальное дополнение от 22.10.2026: [две модели, политика, API и результаты проверки](dual-model.md). Ниже сохранено описание исходного кредитного компонента; утверждения об одной модели и отсутствии новых запусков относятся к историческому снимку до этого дополнения.

Назначение: подготовка и настройки скоринга.

Статус реализации: отдельный локальный ML-сервис; публичный backend и frontend не поставляются. Статус проверки документации — в [verification.md](verification.md).

Актуальность: 22.10.2026. Исходный проверяемый снимок: `ml/local-scoring-runtime` / [`f14d090a956d`](https://github.com/Tonitrus1/ALFA-HACK-2026/commit/f14d090a956d2a9063da57a53c269237b5df6298). Среда исторических runtime-проверок: macOS arm64, Python 3.12.13. При этой миграции сервисы повторно не запускались.

## Проверенная среда и требования

Исходные протоколы относятся к macOS arm64, Python 3.12.13, PostgreSQL 17.5 и CPU. Native setup проверяет Darwin/arm64. Нужны Python 3.12, инструменты сборки Apple и свободные порты 8001/55432. Минимальные RAM, диск и время полной подготовки не измерены. Linux, Windows, Docker и PowerShell не проверены; готовых команд для них нет.

## Первичная подготовка

Сеть требуется: установка закреплённых Python-пакетов и получение/сборка PostgreSQL. Команда создаёт `.venv`, выделенный кластер `.local/pgdata`, роли и БД `credit_scoring_demo`; применяет миграции. Существующую общую БД она не использует.

ОС/оболочка: macOS arm64, POSIX shell. Рабочий каталог: корень соответствующей ветки репозитория.

```sh
./scripts/setup-ml.sh
```

Ожидается сообщение `Standalone ML database prepared` и успешное завершение setup. В репозитории уже есть обученная модель, датасет и подготовленные компании: обучение и отдельный seed перед запуском не нужны. Ссылки: [lock зависимостей](../../../ml/requirements.lock.txt), [миграция](../../../ml/migrations/V1__ml.sql), [bundle](../../../ml/artifacts/baseline/), [данные](data.md).

## Настройки

| Переменная | Назначение | Обязательность | По умолчанию | Секретность |
|---|---|---|---|---|
| PYTHON_BIN | Python для setup | Нет | python3.12 | Нет |
| PYTHONPATH | Импорт scoring при ручном запуске | Для ручного запуска | Launcher задаёт абсолютный путь `ml` | Нет |
| MODEL_BUNDLE | Путь к bundle при ручном запуске | Для ручного запуска | Сервер: `ml/artifacts/baseline`; launcher фиксирует этот каталог | Нет |
| ML_DATABASE_URL | DSN runtime-роли PostgreSQL | Да для сервера | Launcher формирует локальный DSN | Да, пароль |
| ML_INTERNAL_TOKEN | Служебная авторизация | Да, минимум 16 символов | Launcher создаёт случайный токен | Да |
| DATASET_PATH | Датасет при обучении | Нет | `datasets/ru-sme-dataset-10000` | Нет |
| OPENBLAS_NUM_THREADS / OMP_NUM_THREADS | CPU-параллельность | Нет | Launcher задаёт 1 | Нет |

Launcher хранит adminPassword, mlPassword и ML_INTERNAL_TOKEN в исключённом из Git `.local/runtime.json` с правами 0600. Значения не переносить в frontend или README. Переменные для ручного uvicorn не переопределяют жёстко заданные launcher-настройки. Токен backend получает через секреты deployment.

## Запуск

Обычный runtime после подготовки; платных вызовов нет. Если сервис уже запущен, сначала выполните его штатную остановку по [operations](operations.md).

ОС/оболочка: macOS arm64, POSIX shell. Рабочий каталог: корень соответствующей ветки репозитория.

```sh
./scripts/demo up --offline
```

Ожидается локальный сервис на `127.0.0.1:8001` и сообщение о loopback-only режиме. Данные inference сохраняются в PostgreSQL. Ручной запуск uvicorn с собственным PostgreSQL — инженерный вариант, не отдельная подтверждённая платформенная поставка.

## Проверка готовности

Проверка использует собственный локальный токен, не печатает его и не изменяет данные. 200 и `ready: true` означают загрузку модели и доступность ML-хранилища, но не готовность публичного кабинета.

ОС/оболочка: macOS arm64, POSIX shell. Рабочий каталог: корень соответствующей ветки репозитория.

```sh
.venv/bin/python - <<'PY_HEALTH'
import json, urllib.request
from pathlib import Path
cfg = json.loads(Path('.local/runtime.json').read_text())
req = urllib.request.Request('http://127.0.0.1:8001/health',
    headers={'Authorization': 'Bearer ' + cfg['ML_INTERNAL_TOKEN']})
with urllib.request.urlopen(req, timeout=3) as response:
    print(response.status, response.read().decode())
PY_HEALTH
```

## Сеть и автономный режим

Обучение читает локальные файлы. Runtime не обучает и не скачивает модели. `--offline` запускает ML и выделенный PostgreSQL под macOS sandbox с loopback/Unix sockets; источник свидетельства — [исторический runtime-протокол](../../../reports/ml-runtime.json). Внешних платных API нет.

## Типичные ошибки

| Симптом | Причина | Действие |
|---|---|---|
| Setup отвергает ОС | Проверен только macOS arm64 | Подготовить отдельный deployment, не считать этот launcher переносимым |
| 403 на health | Токен не совпал/отсутствует | Передать Bearer из локальной конфигурации |
| Artifact/library mismatch | Bundle или версии не совпали | Проверить manifest/SHA256SUMS и lock; не обходить проверку |
| Not this dedicated cluster | Путь/маркер БД не соответствует проекту | Не менять маркер вручную; подготовить отдельный стенд |
| ML already running | Процесс уже запущен | Использовать штатный down; не завершать произвольный процесс по порту |
