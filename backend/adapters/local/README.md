# adapters/local

Локальные адаптеры профиля `local-mvp` (задача P25, реализованы). Выполняют настоящую работу:

| Порт | Адаптер | Поведение |
| --- | --- | --- |
| SessionStorePort | JdbcSessionAdapter | Долговечные сессии в PostgreSQL: TTL, версия, отзыв, authEpoch |
| CachePort | BoundedLocalCacheAdapter | Ограниченный in-process TTL-кеш производных данных |
| EventTransportPort | PostgresOutboxTransportAdapter | Транзакционный outbox, dispatcher с SKIP LOCKED, inbox |
| ObjectStorePort | VersionedFilesystemObjectAdapter | Неизменяемые версии файлов в томах quarantine/clean + метаданные в БД |

Контрактные случаи проверяет `app/src/test/.../adapters/LocalAdapterContractTest` (TTL, размер, версия, tenant-ключи; карантин, unsafe, oversize, traversal, digest mismatch, stale ref, restart; доставка/сбой события), выбор провайдера — `CompositionRootTest`.

Спецификация: [technology-adapters.json](../../../docs/architecture/contracts/technology-adapters.json).
