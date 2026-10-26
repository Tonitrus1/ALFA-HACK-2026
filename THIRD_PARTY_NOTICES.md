# Third-party notices · Поток

Комплект команды Gambit_Yvaga, 26.10.2026. Этот файл описывает фактическую интеграционную поставку; старые notices в `docs/architecture` относятся к архитектурному пакету, а notices standalone-модулей могут описывать их первоначальный способ запуска. При расхождении профиль текущего приложения определяется Compose и соответствующими lock-файлами.

## Код, инфраструктура и зависимости

| Компонент | Назначение | Лицензия / источник версий |
|---|---|---|
| Java / Eclipse Temurin / OpenJDK 21 | JVM backend | GPL-2.0 with Classpath Exception; [OpenJDK](https://openjdk.org/legal/gplv2+ce.html), Dockerfile backend |
| Spring Boot 4.1.1 / Spring Framework, Flyway Community, Apache Maven | Backend / миграции / сборка | Apache-2.0; `backend/pom.xml`, `.mvn/wrapper/maven-wrapper.properties` |
| PostgreSQL 17, JDBC driver | Бизнес- и ML-хранилища | PostgreSQL License / BSD-2-Clause driver; Compose и Maven dependency tree |
| React 19, React Router, TypeScript, Vite, Ant Design, React Query, React Hook Form, Zod, Lucide | Веб-интерфейс | MIT, Lucide ISC; точные зависимости и транзитивные версии в `frontend/package-lock.json` |
| Nginx | Gateway и статические файлы | BSD-2-Clause; `deploy/Dockerfile.gateway` |
| Python 3.12 | ML / AI runtime | PSF; Dockerfiles |
| FastAPI, Pydantic, HTTPX, AnyIO, SQLAlchemy, Alembic | API, схемы, HTTP, хранение | MIT; версии соответствующего lock-файла |
| Uvicorn | ASGI server | BSD-3-Clause |
| NumPy, SciPy, pandas, scikit-learn, joblib | Подготовка данных и inference | BSD-3-Clause для NumPy/SciPy/pandas/scikit-learn; joblib BSD-3-Clause |
| CatBoost, Optuna | Модель риска / экспериментальное ранжирование / обучение | Apache-2.0 / MIT |
| PyTorch, transformers, sentence-transformers, huggingface-hub | Локальные embeddings, tokenizer, подготовка моделей | PyTorch BSD-3-Clause; HF libraries Apache-2.0 |
| OpenAI Python SDK | Клиент OpenAI-compatible API | Apache-2.0; SDK сам по себе не означает использование модели OpenAI |
| rank-bm25 | Лексический поиск | Apache-2.0 |
| Qdrant / qdrant-client | Dense-индекс знаний | Apache-2.0; закреплённый image/digest в Compose |
| SQLite | Знания и журналы OCR | Public domain |
| SearXNG | Self-hosted веб-поиск | AGPL-3.0-or-later; [исходники](https://github.com/searxng/searxng), image/digest в Compose |
| Tesseract / pytesseract / rus+eng traineddata | OCR по умолчанию | Apache-2.0; исходники [Tesseract](https://github.com/tesseract-ocr/tesseract), данные [tessdata_fast](https://github.com/tesseract-ocr/tessdata_fast) |
| PaddleOCR / PaddlePaddle / PaddleX и OCR weights | Дополнительный standalone OCR-профиль | Apache-2.0; `ml/ocr/THIRD_PARTY_NOTICES.md`, hashes модели. Не default интеграции |
| PyMuPDF / MuPDF | PDF rendering и inspection в OCR | AGPL-3.0 либо коммерческая лицензия; [условия](https://pymupdf.readthedocs.io/en/latest/about.html#license). Для банковского внедрения требуется учесть выбранный способ использования/распространения |
| Pillow, jsonschema, pypdf, trafilatura | Изображения, схемы, PDF/text/HTML | Pillow MIT-CMU, jsonschema MIT, pypdf BSD-3-Clause, trafilatura Apache-2.0 |
| ClamAV | Настоящая антивирусная проверка | GPL-2.0; [исходники](https://github.com/Cisco-Talos/clamav), image `clamav/clamav:1.4` |
| Ollama | Опциональный полностью локальный LLM runtime | MIT; [исходники](https://github.com/ollama/ollama), image `0.34.0`; лицензия runtime не заменяет лицензию весов |
| Caddy | Дополнительный Selectel TLS edge | Apache-2.0; `deploy/selectel/compose.yaml` |
| Docker / Compose / Linux image packages | Сборка и запуск | Компоненты под собственными лицензиями. Для Docker Desktop действуют условия его поставки. Copyright/license отдельных Debian/Alpine пакетов сохраняются в образах |
| pytest, Ruff, uv, Vitest, Playwright, ESLint, ArchUnit, embedded-postgres | Разработка и проверки | pytest/Vitest/ESLint MIT, Playwright/ArchUnit Apache-2.0, uv/Ruff MIT или Apache-2.0, embedded-postgres Apache-2.0; точные версии в locks/pom |

Полные транзитивные версии: `frontend/package-lock.json`, `ml/requirements.lock.txt`, `ml/feed/requirements.lock.txt`, `ml/feed_v2/requirements.lock.txt`, `ml/assistant/uv.lock`, `ml/ocr/uv.lock`. Python AI-модули фиксируют direct dependencies также в `pyproject.toml`; Maven управляет Java-версиями через Spring Boot BOM и pom. Условия транзитивных CUDA/NVIDIA пакетов приведены в [assistant notices](ml/assistant/THIRD_PARTY_NOTICES.md); CPU inference не превращает их лицензии в Apache/MIT.

## Модели и данные

| Актив | Использование и происхождение | Условия |
|---|---|---|
| `intfloat/multilingual-e5-small` | Feed и RAG embeddings, без обучения на пользовательских данных | MIT. Feed revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`; assistant revision `fd1525a9fd15316a2d503bf26ab031a61d056e98`. SHA256/locks в соответствующих модулях |
| `Qwen2.5-3B-Instruct` / Ollama `qwen2.5:3b` | Открытые веса для local RAG/OCR; скачиваются при подготовке, не включены в Git | **Qwen RESEARCH LICENSE**, исследование/оценка, коммерческое использование требует отдельного разрешения. Не Apache-2.0. [Лицензия производителя](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct/blob/main/LICENSE), [Ollama package](https://ollama.com/library/qwen2.5:3b) |
| Qwen3 tokenizer / внешний development profile | Совместимый альтернативный provider profile; не default проверяемого local-профиля | Условия конкретной выбранной модели, revision tokenizer в конфигурации. Не переносить лицензию одной Qwen на все размеры/семейства |
| CatBoost risk baseline | Собственный обученный bundle `ml/artifacts/baseline`, `SYNTHETIC_FINANCE_V1`, score `BANKRUPTCY_PROXY` | Артефакт проекта, контрольные суммы и model card. Синтетическая метрика не является банковской PD |
| Scoring v2 / fraud-demo-v1 / Feed v2 ranker | Исследовательские артефакты с manifests и evaluation | Явно выбранные кандидаты/эксперименты; наличие в Git не означает default или банковское одобрение |
| `datasets/ru-sme-dataset-10000` | Авторский синтетический набор компаний и финансов, описание и генераторы в репозитории | Используется для демонстрации/исследования, не выгрузка реальных клиентов |
| Feed articles / illustrations | Авторский демонстрационный каталог и SVG | Вымышленные ситуации, не актуальные банковские ставки/оферты |
| Assistant corpus | Авторские краткие заметки и ссылки на публичные первоисточники; синтетические документы исключены из ответов клиентам | Права на исходные страницы у их владельцев. Полные тексты сторонних сайтов не считаются автоматически разрешёнными к распространению |
| Синтетические документы OCR и тестовые fixtures | Генераторы/файлы проекта | Только искусственные данные, не финансовая отчётность реальных клиентов |
| DejaVu Sans | Синтетические документы и вспомогательные схемы | DejaVu/Bitstream Vera font license; оригинальный notice в архитектурном пакете |

Qwen is licensed under the Qwen RESEARCH LICENSE AGREEMENT, Copyright (c) Alibaba Cloud. All Rights Reserved.

Проверяемая хакатонная версия использует локальные открытые веса и не требует платного API. Для коммерческого банковского внедрения необходимо выбрать модель с подходящими условиями либо получить разрешение, затем повторить оценку качества и ресурсов. Исходные веса не переупаковываются в этот репозиторий.

## Внешние сервисы и моделирование

- **ngrok:** реальный туннель для демонстрации, сервисные условия [ngrok](https://ngrok.com/terms-of-service). Не часть банковской архитектуры высокой доступности и не требуется для локального запуска.
- **GitHub / Actions:** размещение исходников, история и CI, условия GitHub. Локальный runtime не вызывает GitHub для обработки заявки.
- **Hugging Face / Ollama registry:** первичная загрузка закреплённых моделей. Повторный запуск использует сохранённые volumes.
- **SearXNG upstream engines:** внешний поиск зависит от сети и условий соответствующих источников, доступность не гарантируется.
- **AITUNNEL / другие OpenAI-compatible API:** реальный опциональный development-профиль, может быть платным. Не является обязательной зависимостью бесплатной сдаваемой версии. Алиас провайдера сам по себе не подтверждает identity/revision модели.
- **Смоделированы:** компании/учётные записи и финансы, продуктовые ограничения, Java-кредитная политика, подписание и выдача. Интеграции с БКИ, KYC/AML, АБС и ЭП не подключены. Redis/Kafka/S3 каркасы не объявляются работающими сервисами.

Визуальный стиль презентации создан по предоставленному кейсу Альфа Хак. Товарные знаки Альфа-Банка/«Альфа Будущее» принадлежат владельцам; авторство продукта и сдаваемого комплекта указано за командой Gambit_Yvaga.
