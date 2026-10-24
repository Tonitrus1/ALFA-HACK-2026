# Архитектура сервиса

```mermaid
flowchart LR
    Client[Swagger / HTTP клиент] --> API[FastAPI /v1]
    API --> Sessions[Память: TTL, токен, блокировка, кеш]
    API --> Agent[Ограниченный цикл агента]
    Agent --> LLM[OpenAI-compatible adapter]
    LLM --> Provider[Внешний платный AITUNNEL / Qwen]
    Agent --> KB[KnowledgeService: E5 + BM25 + RRF]
    KB --> SQLite[(SQLite: источник истины)]
    KB --> Qdrant[(Qdrant: производный индекс)]
    KB --> Originals[(Файлы оригиналов)]
    Agent --> Search[SearXNG]
    Agent --> Reader[Проверяемый HTTP-загрузчик]
    Reader --> Candidates[(Временные снимки)]
    Admin[Администратор] --> Confirm[Просмотр + подтверждение SHA-256]
    Confirm --> KB
    Agent --> Bank[Синтетический BankGateway]
    Agent --> Calculator[Decimal-калькулятор]
```

Интерфейсы `LLMClient`, `SessionStore`, `KnowledgeRepository`, `VectorIndex`,
`WebSearch`, `BankGateway` находятся в `interfaces.py`. API / orchestrator принимают
реализации через фабрику приложения. Обычные тесты подменяют внешние зависимости.
Ни один инструмент не отправляет заявку и не меняет кредитное решение.

```mermaid
erDiagram
    KnowledgeDocument ||--o{ KnowledgeVersion : versions
    KnowledgeVersion ||--o{ KnowledgeChunk : chunks
    Session ||--o{ WebCandidate : owns
    WebCandidate }o--o| KnowledgeVersion : confirms_snapshot
    KnowledgeDocument { string id PK }
    KnowledgeVersion {
        string id PK
        string document_id FK
        int version
        string state
        string sha256
        string original_path
        text text
        json attributes
        string published_at
        string error_code
    }
    KnowledgeChunk {
        string id PK
        string version_id FK
        text text
        int page
        string section
        int ordinal
    }
    WebCandidate {
        string id PK
        string session_id
        string sha256
        text text
        string state
        json knowledge_ref
    }
```

Session - только память процесса; её связь с кандидатом не является внешним ключом БД.
После рестарта все незавершённые кандидаты удаляются. Подтверждённые знания остаются.
Версионный номер уникален в пределах документа. Содержимое версии и исходный файл
неизменяемы; состояние и время публикации обновляются.

```mermaid
stateDiagram-v2
    [*] --> DRAFT: импорт и разбиение
    DRAFT --> PUBLISHED: успешная индексация + подтверждение
    DRAFT --> FAILED: сбой индекса
    FAILED --> PUBLISHED: безопасный повтор
    PUBLISHED --> REVOKED: отзыв или новая версия
```

Публикация, отзыв, ingestion и поиск согласуются `threading.RLock` в одном процессе.
До commit PUBLISHED в SQLite Qdrant должен подтвердить запись всех фрагментов.
Частично записанные точки FAILED/DRAFT никогда не участвуют в поиске: dense фильтрует
по списку активных version_id из SQLite, BM25 строится из того же набора. Старые точки
могут оставаться в Qdrant до reindex, но недоступны поиску. Сверка при старте полностью
перестраивает индекс. Перед выдачей ответа версии перепроверяются. Ходы, контекст которых
зависел от уже неактивной версии, целиком исключаются из последующих LLM-запросов,
включая сохранённые результаты инструментов. Публичная история сессии остаётся доступной
до её закрытия или TTL.

CPU embeddings, parsing, BM25 и SQL-операции выполняются в ограниченном AnyIO thread
pool. Источники ранжируются двумя top-10 ветками и RRF(k=60), top-5. Порог dense
подбирается CLI на опубликованном стартовом корпусе; без измерения dense выключен.
Отдельный запрос к LLM для query expansion или суммаризации не выполняется.

Состояния синтетических заявок не изменяются сервисом: `DOCUMENTS_REQUIRED`,
`UNDER_REVIEW`, `APPROVED`, `DECLINED` читаются из fixtures. Полная диаграмма кредитного
процесса находится в существующей архитектуре основного проекта.
