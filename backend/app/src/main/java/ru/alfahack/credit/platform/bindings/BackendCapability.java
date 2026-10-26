package ru.alfahack.credit.platform.bindings;

import java.util.Set;

/** Способности, которыми владеет backend, и допустимые провайдеры из adapter-bindings.schema.json. */
public enum BackendCapability {

    SESSIONS("sessions", "JdbcSessionAdapter", "RedisSessionAdapter"),
    CACHE("cache", "BoundedLocalCacheAdapter", "RedisCacheAdapter"),
    EVENTS("events", "PostgresOutboxTransportAdapter", "KafkaEventTransportAdapter"),
    OBJECTS("objects", "VersionedFilesystemObjectAdapter", "S3ObjectStoreAdapter");

    private final String key;
    private final Set<String> providers;

    BackendCapability(String key, String localProvider, String realProvider) {
        this.key = key;
        this.providers = Set.of(localProvider, realProvider);
    }

    public String key() {
        return key;
    }

    public Set<String> providers() {
        return providers;
    }
}
