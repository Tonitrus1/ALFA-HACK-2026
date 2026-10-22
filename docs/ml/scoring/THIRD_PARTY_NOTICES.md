# Сторонние компоненты скоринга

Назначение: сторонние компоненты скоринга.

Статус реализации: отдельный локальный ML-сервис; публичный backend и frontend не поставляются. Статус проверки документации — в [verification.md](verification.md).

Актуальность: 22.10.2026. Исходный проверяемый снимок: `ml/local-scoring-runtime` / [`f14d090a956d`](https://github.com/Tonitrus1/ALFA-HACK-2026/commit/f14d090a956d2a9063da57a53c269237b5df6298). Среда исторических runtime-проверок: macOS arm64, Python 3.12.13. При этой миграции сервисы повторно не запускались.

## Компоненты и способы получения

| Компонент | Версия/revision | Источник | Лицензия/условия | Роль | Получение |
|---|---|---|---|---|---|
| CatBoost | 1.2.8 | [CatBoost](https://catboost.ai) | Apache-2.0 (metadata) | Активная модель | pip по lock |
| Optuna | 4.3.0 | [Optuna](https://github.com/optuna/optuna) | MIT; дополнительные notices в LICENSE_THIRD_PARTY | Подбор параметров offline | pip по lock |
| scikit-learn | 1.6.1 | [scikit-learn](https://scikit-learn.org) | BSD-3-Clause (metadata) | CV и метрики | pip по lock |
| SciPy | 1.15.3 | [SciPy](https://scipy.org) | BSD-3-Clause; bundled-компоненты имеют собственные notices | Численные зависимости | pip по lock |
| PyArrow | 20.0.0 | [PyArrow](https://arrow.apache.org) | Apache Software License (metadata) | Чтение Parquet | pip по lock |
| joblib | 1.6.0 | [joblib](https://github.com/joblib/joblib) | BSD-3-Clause (metadata) | Serialization | pip по lock |
| Psycopg / psycopg-binary | 3.2.9 | [Psycopg / psycopg-binary](https://www.psycopg.org/psycopg3/) | LGPLv3 для psycopg; проверить bundled libpq/OpenSSL notices отдельно | PostgreSQL driver | pip по lock |
| PostgreSQL | 17.5 | [PostgreSQL](https://www.postgresql.org) | PostgreSQL License; COPYRIGHT исходного дистрибутива | Хранилище ML | setup получает официальный source tar и проверяет hash |
| NumPy | 2.2.6 | [NumPy](https://numpy.org) | BSD-3-Clause; в дистрибутиве также bundled notices | Матрицы и численные операции | pip по lock |
| FastAPI | 0.115.12 | [FastAPI](https://github.com/fastapi/fastapi) | MIT (LICENSE установленного пакета) | HTTP API | pip по lock |
| Pydantic | 2.14.1 | [Pydantic](https://github.com/pydantic/pydantic) | MIT (metadata) | Схемы входа/выхода | pip по lock |
| Uvicorn | 0.34.3 | [Uvicorn](https://www.uvicorn.org) | BSD-3-Clause (metadata) | ASGI runtime | pip по lock |

Полный перечень точных Python-зависимостей и транзитивных пакетов: [requirements.lock.txt](../../../ml/requirements.lock.txt). Таблица перечисляет ключевые runtime/ML-компоненты, а не объявляет исчерпывающий лицензионный аудит всех bundled-библиотек. Лицензии извлечены из поставленных metadata/LICENSE, неизвестные явно отмечены. Ссылки — upstream-источники, новая загрузка и юридическая проверка сайтов не выполнялись.

## Данные и собственные материалы

Корпоративные реквизиты — открытый реестр МСП ФНС; [паспорт и provenance](data.md). Условия источника не заменяются лицензией CatBoost. Собственные синтетические финансы/labels/веса не получили автоматически лицензию upstream-библиотеки; отдельная открытая лицензия проекта не объявлена. Полный binary prefix с посторонними ИП не поставляется.

## Внешние API и стоимость

Платных inference API в этом сервисе нет. Сеть нужна при установке/подготовке, а не для модельного runtime. Получение открытых весов/пакетов не означает передачу им пользовательских финансов или профилей во время работы. Условия registry/model host и права на собственные материалы проверять перед внешним распространением.

## Обновления и ограничения проверки

При смене revision/версии повторно собрать перечень и сохранить upstream notices вместе с артефактами. Неподтверждённая лицензия не считается разрешением на распространение. Полная проверка совместимости лицензий и bundled-компонентов при этой миграции не проводилась.
