# adapters/kafka

Kafka: `KafkaEventTransportAdapter` (EventTransportPort). Outbox остаётся источником; Kafka только ретранслирует закоммиченные сообщения.

Статус: `SPECIFIED_NOT_IMPLEMENTED`. Каркас бросает `ProviderNotImplemented` при выборе и не возвращает фиктивных результатов.
Подключение — отдельная задача (P27, профиль `local-integrations`): закрепить версии SDK/сервера (P02), пройти общие контрактные проверки порта и проверки конкретного сервиса.
Спецификация: [technology-adapters.md](../../../docs/architecture/docs/technology-adapters.md), [technology-adapters.json](../../../docs/architecture/contracts/technology-adapters.json).
