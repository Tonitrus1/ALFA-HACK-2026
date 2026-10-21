# Отличия от прежнего assistant-контракта

Источник сравнения: `docs/architecture/contracts/internal.openapi.json`,
`POST /internal/v2/assistant/answers`, схемы MLAssistantInput / MLAssistantResponse.
Эти опубликованные проектные контракты данным этапом не изменяются.

| Прежняя спецификация | Отдельный сервис | Работа будущего адаптера |
|---|---|---|
| conversationId, message, серверный snapshot проекта | session_id и session_token, только новое message + client_message_id | Создавать сессии по доверенной аутентификации Java, хранить токен на сервере |
| conversationId / messageId | session_id / message_id | Явное сопоставление полей |
| ANSWER / INSUFFICIENT_EVIDENCE / SEARCH_ONLY | Те же три статуса, ошибки отдельным HTTP envelope | Сохранить семантику, преобразовать ошибки |
| MLCitation и release/bundle привязка | KNOWLEDGE (document_id, version_id, version, page) или WEB (URL, retrieved_at) | Расширить публичную схему для WEB, проверять допустимость внешних ссылок |
| releaseId, bundleDigest, kbEpoch обязательны | Пока не существуют | Обеспечить настоящий release manifest; не выдумывать значения |
| История по прежней архитектуре | Только память процесса, TTL 60 минут, до 100 сессий | Явно согласовать потерю диалога после рестарта |
| Фиксированный bundle промпта | UTF-8 файл, admin override, hash на сессию | Определить политику версий и административный доступ |
| Нет подтверждения веб-снимка | pending_actions и отдельный admin confirm по SHA-256 | Добавить UI подтверждения и права администратора |
| Технический usage не задан этим ответом | usage, estimated_cost_rub, latency_ms, request_id, context_truncated | Не раскрывать секреты; решить, какие метрики видит клиент |

Совместимость без адаптера не заявляется. Изменение общих контрактов следует провести
отдельным PR с владельцами Java и интеграции по CONTRIBUTING.md.
В этом этапе нет реального Java BankGateway. Синтетический demo_user_id назначается
сервером, переопределяется только администратором; модель не задаёт компанию.
