# Сторонние компоненты ленты

Назначение: сторонние компоненты ленты.

Статус реализации: отдельный локальный ML-сервис; публичный backend и frontend не поставляются. Статус проверки документации — в [verification.md](verification.md).

Актуальность: 22.10.2026. Исходный проверяемый снимок: `ml/feed-recommendations` / [`829c1c09bb24`](https://github.com/Tonitrus1/ALFA-HACK-2026/commit/829c1c09bb248f03d730f25526de3b11712370bd). Среда исторических runtime-проверок: macOS arm64, Python 3.12.13. При этой миграции сервисы повторно не запускались.

## Компоненты и способы получения

| Компонент | Версия/revision | Источник | Лицензия/условия | Роль | Получение |
|---|---|---|---|---|---|
| multilingual-e5-small | 614241f622f53c4eeff9890bdc4f31cfecc418b3 | [multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small/tree/614241f622f53c4eeff9890bdc4f31cfecc418b3) | MIT (YAML закреплённой model card) | Модель и tokenizer | prepare --download с SHA256 |
| PyTorch | 2.6.0 | [PyTorch](https://pytorch.org) | BSD-3-Clause (metadata); bundled notices отдельно | CPU inference | pip по lock |
| Transformers | 4.51.3 | [Transformers](https://github.com/huggingface/transformers) | Apache-2.0 (metadata) | Загрузка E5/tokenizer | pip по lock |
| huggingface-hub | 0.30.2 | [huggingface-hub](https://github.com/huggingface/huggingface_hub) | Apache (metadata) | Явная подготовка из upstream | pip по lock |
| safetensors | 0.5.3 | [safetensors](https://github.com/huggingface/safetensors) | Apache-2.0 ([LICENSE v0.5.3](https://github.com/safetensors/safetensors/blob/v0.5.3/LICENSE)) | Чтение весов | pip по lock |
| tokenizers | 0.21.4 | [tokenizers](https://github.com/huggingface/tokenizers) | Apache-2.0 ([LICENSE v0.21.4](https://github.com/huggingface/tokenizers/blob/v0.21.4/LICENSE)) | Токенизация | pip по lock |
| HTTPX | 0.28.1 | [HTTPX](https://www.python-httpx.org) | BSD-3-Clause (metadata) | Клиент backend | pip по lock |
| NumPy | 2.2.6 | [NumPy](https://numpy.org) | BSD-3-Clause; в дистрибутиве также bundled notices | Матрицы и численные операции | pip по lock |
| FastAPI | 0.115.12 | [FastAPI](https://github.com/fastapi/fastapi) | MIT (LICENSE установленного пакета) | HTTP API | pip по lock |
| Pydantic | 2.14.1 | [Pydantic](https://github.com/pydantic/pydantic) | MIT (metadata) | Схемы входа/выхода | pip по lock |
| Uvicorn | 0.34.3 | [Uvicorn](https://www.uvicorn.org) | BSD-3-Clause (metadata) | ASGI runtime | pip по lock |

Полный перечень точных Python-зависимостей и транзитивных пакетов: [requirements.lock.txt](../../../ml/feed/requirements.lock.txt). Таблица перечисляет ключевые runtime/ML-компоненты, а не объявляет исчерпывающий лицензионный аудит всех bundled-библиотек. Лицензии извлечены из поставленных metadata/LICENSE, неизвестные явно отмечены. Ссылки — upstream-источники. Для safetensors/tokenizers 22.10.2026 прочитаны LICENSE точных тегов v0.5.3/v0.21.4 через GitHub API; веса и пакеты при оформлении не скачивались. Полная юридическая проверка не выполнялась.

## Данные и собственные материалы

Собственные карточки, вымышленные примеры и SVG: отдельная открытая лицензия не объявлена. Источники общих принципов — [British Business Bank: cash flow](https://www.british-business-bank.co.uk/business-guidance/guidance-articles/finance/how-to-create-a-cash-flow-forecast-in-4-steps), [сезонность](https://www.british-business-bank.co.uk/business-guidance/guidance-articles/finance/protecting-your-cash-flow-from-seasonality), [SBA: startup costs](https://www.sba.gov/blog/2017/2017-01/how-estimate-starting-costs/). Из них не переносились иностранные банковские правила или полный текст. Model MIT не лицензирует автоматически каталог.

## Внешние API и стоимость

Платных inference API в этом сервисе нет. Сеть нужна при установке/подготовке, а не для модельного runtime. Получение открытых весов/пакетов не означает передачу им пользовательских финансов или профилей во время работы. Условия registry/model host и права на собственные материалы проверять перед внешним распространением.

## Обновления и ограничения проверки

При смене revision/версии повторно собрать перечень и сохранить upstream notices вместе с артефактами. Неподтверждённая лицензия не считается разрешением на распространение. Полная проверка совместимости лицензий и bundled-компонентов при этой миграции не проводилась.
