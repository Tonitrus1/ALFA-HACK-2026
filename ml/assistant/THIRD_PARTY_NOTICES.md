# Сторонние компоненты и симуляторы

Версии Python-пакетов и транзитивных зависимостей фиксируются `uv.lock`.
Внешние образы закреплены тегами и проверенными OCI digest в Dockerfile/Compose.
Собственный образ имеет тег `alfa-assistant:0.1.0-dev` и собирается из локального кода.

| Компонент | Назначение | Лицензия / условия |
|---|---|---|
| Python 3.12 | Runtime | PSF |
| FastAPI, Pydantic / pydantic-settings, HTTPX, AnyIO | API / схемы / HTTP / потоки | MIT |
| Uvicorn | ASGI | BSD-3-Clause |
| OpenAI Python SDK | Совместимый клиент Chat Completions, не выбор модели OpenAI | Apache-2.0 |
| SQLAlchemy, Alembic | SQLite ORM / миграции | MIT |
| SQLite | Долговременное хранилище | Public domain |
| qdrant-client / Qdrant | Векторный индекс | Apache-2.0 |
| rank-bm25 | Лексический поиск | Apache-2.0 |
| pypdf | Текстовые PDF | BSD-3-Clause |
| trafilatura | HTML extraction | Apache-2.0 |
| python-multipart | Загрузка файлов | Apache-2.0 |
| sentence-transformers, transformers, huggingface-hub | Локальные модели / tokenizer | Apache-2.0 |
| PyTorch | CPU inference E5 | BSD-3-Clause |
| NVIDIA CUDA runtime libraries (`nvidia-*` in uv.lock, Linux PyPI dependency of torch) | Устанавливаются стандартным Linux wheel PyTorch; при CPU inference не используются | Собственные условия NVIDIA; [официальная лицензия](https://docs.nvidia.com/cuda/eula/index.html), LICENSE внутри соответствующих wheels |
| Triton | Транзитивная Linux-зависимость PyTorch | MIT |
| intfloat/multilingual-e5-small | Embeddings, 384, MIT | [Модель](https://huggingface.co/intfloat/multilingual-e5-small), revision fd1525a9fd15316a2d503bf26ab031a61d056e98 |
| Qwen/Qwen3-30B-A3B | Открытые веса; здесь локально только tokenizer | [Apache-2.0](https://huggingface.co/Qwen/Qwen3-30B-A3B), tokenizer revision ad44e777bcd18fa416d9da3bd8f70d33ebb85d39 |
| AITUNNEL | Внешний платный сервис разработки | [Условия сервиса](https://aitunnel.ru/), API ключ пользователя; не для проверяемой бесплатной версии |
| SearXNG | Бесплатный self-hosted поиск | AGPL-3.0-or-later; [исходники](https://github.com/searxng/searxng) |
| DuckDuckGo / Bing | Внешние источники поисковой выдачи | Условия соответствующих поисковиков, доступность не гарантируется |
| uv / Ruff / pytest / pytest-asyncio | Сборка / lint / проверки | uv и Ruff MIT/Apache-2.0, pytest MIT, pytest-asyncio Apache-2.0 |

Не копировать полные тексты банковских сайтов без проверки условий. В `corpus/manifest.json`
пять публичных источников представлены ссылками и авторскими краткими заметками,
а не полными копиями. Права на исходные страницы остаются у владельцев; разрешение
на их полное распространение не установлено. Автоматическое сохранение веб-снимка
требует ввода администратором атрибуции и допустимого использования.

Смоделированы: две компании, два пользователя, четыре заявки, три продукта и их
документы. Это авторские fixtures проекта. Интеграции с корпоративными системами,
скорингом, выдачей и подписанием отсутствуют. Расчёт аннуитета - детерминированная
демонстрационная формула, не банковское предложение.
