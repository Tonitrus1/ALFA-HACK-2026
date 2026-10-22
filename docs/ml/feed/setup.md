# Подготовка и настройки ленты

Назначение: подготовка и настройки ленты.

Статус реализации: отдельный локальный ML-сервис; публичный backend и frontend не поставляются. Статус проверки документации — в [verification.md](verification.md).

Актуальность: 22.10.2026. Исходный проверяемый снимок: `ml/feed-recommendations` / [`829c1c09bb24`](https://github.com/Tonitrus1/ALFA-HACK-2026/commit/829c1c09bb248f03d730f25526de3b11712370bd). Среда исторических runtime-проверок: macOS arm64, Python 3.12.13. При этой миграции сервисы повторно не запускались.

## Проверенная среда и требования

Исторические протоколы: macOS 14.5 arm64, Python 3.12.13, CPU, четыре потока E5. Требуются порт 8002, Python 3.12 и сеть при первичной подготовке. Веса примерно 449 MiB, векторы каталога малы; минимальные RAM/диск и холодный startup не измерены. Windows/PowerShell, Linux, Docker и GPU deployment не проверены, команд для них эта инструкция не утверждает.

## Первичная подготовка

Команды с сетью создают отдельную `.venv-feed`, устанавливают lock и загружают только файлы закреплённой ревизии. Они создают `.local/feed-bundle`, не меняя PostgreSQL и окружение рисковика.

ОС/оболочка: macOS arm64, POSIX shell. Рабочий каталог: корень соответствующей ветки репозитория.

```sh
./scripts/feed setup
./scripts/feed prepare --download
```

Ожидается подготовленный manifest, embeddings и model/ с корректными SHA256. [Lock зависимостей](../../../ml/feed/requirements.lock.txt), [model-lock](../../../ml/feed/model-lock.json), [release](../../../ml/feed/release/). Без `--download` prepare использует только уже имеющиеся файлы. Не отключайте проверку TLS/hash при ошибке.

## Настройки

| Переменная | Назначение | Обязательность | По умолчанию | Секретность |
|---|---|---|---|---|
| PYTHON_BIN | Python для setup | Нет | python3.12 | Нет |
| ML_INTERNAL_TOKEN | Токен backend → FEED | Да, минимум 16 символов | Нет; задаёт оператор | Да |
| FEED_BUNDLE | Путь к runtime-комплекту | Нет | `.local/feed-bundle` | Нет |
| FEED_CPU_THREADS | CPU-потоки модели | Нет | 4 | Нет |
| HF_HUB_OFFLINE / TRANSFORMERS_OFFLINE | Запрет сетевых загрузок runtime | Launcher задаёт | 1 при serve | Нет |
| TOKENIZERS_PARALLELISM | Внутренняя параллельность tokenizer | Launcher задаёт | false | Нет |

Токен не сохраняется самим FEED; задайте его из секретов deployment. Для локальной проверки можно создать новый токен командой ниже. Она не печатает значение, но смена токена требует того же значения у backend. Не используйте токен скоринга только потому, что переменная называется одинаково.

ОС/оболочка: macOS arm64, POSIX shell. Рабочий каталог: корень соответствующей ветки репозитория.

```sh
export ML_INTERNAL_TOKEN="$(.venv-feed/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))')"
```

## Запуск

Обычный runtime после подготовки, без сети и платных API. Команда занимает foreground, слушает loopback:8002.

ОС/оболочка: macOS arm64, POSIX shell. Рабочий каталог: корень соответствующей ветки репозитория.

```sh
./scripts/feed serve
```

Ожидается готовый процесс uvicorn. Если bundle повреждён/отсутствует, процесс может быть запущен, но `/health` вернёт 503: открытый порт не означает readiness. `--host` для отдельного deployment допускается uvicorn, но сетевую изоляцию и токен обеспечивает оператор; такой deployment здесь не проверялся.

## Проверка готовности

В другой POSIX-shell с тем же ML_INTERNAL_TOKEN, без записи пользовательских данных:

ОС/оболочка: macOS arm64, POSIX shell. Рабочий каталог: корень соответствующей ветки репозитория.

```sh
curl --fail-with-body -H "X-Service-Token: ${ML_INTERNAL_TOKEN}" http://127.0.0.1:8002/health
```

Ожидается HTTP 200, ready=true, catalogVersion/catalogDigest/releaseId. Без правильного заголовка — 403; пока нет модели — 503. Bearer для FEED не подходит. [Контракт](integration.md).

## Сеть и автономный режим

Установка и `prepare --download` требуют сети. Во время serve/rank/test используются локальные веса, `local_files_only=True`, CPU/eval/inference mode; downloads отключены. Для полностью автономной машины перенесите проверенный `.local/feed-bundle` и заранее подготовленные зависимости. Внешней LLM и платных inference API нет. Доказательство OS-level запрета сети в историческом стенде — [HTTP smoke](../../../reports/feed-http-smoke.json); обычная команда serve сама не устанавливает macOS OS-sandbox.

## Типичные ошибки

| Симптом | Причина | Действие |
|---|---|---|
| 403 | Неверный X-Service-Token | Передать backend/FEED одинаковое секретное значение |
| 503/health при живом процессе | Нет модели/ошибка hashes или library versions | Подготовить корректный комплект; backend применяет RULES |
| 409 | Каталог, кандидат, текст или Idempotency-Key не совпал | Сверить exact request и закреплённые версии |
| 422 | Неизвестный enum/поле, дубли/пустые IDs | Исправить типизированный профиль и кандидатов |
| Модель пытается скачаться | Запущена неверная подготовка/путь | Использовать проверенный bundle; сеть не нужна для serve |
