package ru.alfahack.credit.platform.bindings;

import java.nio.file.Path;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.jdbc.core.simple.JdbcClient;

import ru.alfahack.credit.adapters.kafka.KafkaEventTransportAdapter;
import ru.alfahack.credit.adapters.local.BoundedLocalCacheAdapter;
import ru.alfahack.credit.adapters.local.JdbcSessionAdapter;
import ru.alfahack.credit.adapters.local.PostgresOutboxTransportAdapter;
import ru.alfahack.credit.adapters.local.VersionedFilesystemObjectAdapter;
import ru.alfahack.credit.adapters.redis.RedisCacheAdapter;
import ru.alfahack.credit.adapters.redis.RedisSessionAdapter;
import ru.alfahack.credit.adapters.s3.S3ObjectStoreAdapter;
import ru.alfahack.credit.ports.cache.CachePort;
import ru.alfahack.credit.ports.events.EventSink;
import ru.alfahack.credit.ports.events.EventTransportPort;
import ru.alfahack.credit.ports.objects.ObjectStorePort;
import ru.alfahack.credit.ports.sessions.SessionStorePort;

/**
 * Composition root (P25): ровно одна реализация на способность по {@link AdapterBindings}. Выбор
 * неподключённого провайдера останавливает запуск; автоматического переключения при отказе нет.
 */
@Configuration(proxyBeanMethods = false)
class AdapterBindingsConfiguration {

    @Bean
    AdapterBindings adapterBindings(AdapterBindingsProperties properties) {
        return AdapterBindings.of(
                properties.profile(), properties.automaticProviderFallback(), properties.bindings());
    }

    @Bean
    SessionStorePort sessionStorePort(AdapterBindings bindings, JdbcClient jdbcClient) {
        return switch (bindings.provider(BackendCapability.SESSIONS)) {
            case "JdbcSessionAdapter" -> new JdbcSessionAdapter(jdbcClient);
            case "RedisSessionAdapter" -> RedisSessionAdapter.create();
            default -> throw unsupported(BackendCapability.SESSIONS);
        };
    }

    @Bean
    CachePort cachePort(AdapterBindings bindings, @Value("${credit.cache.max-entries:10000}") int maxEntries) {
        return switch (bindings.provider(BackendCapability.CACHE)) {
            case "BoundedLocalCacheAdapter" -> new BoundedLocalCacheAdapter(maxEntries);
            case "RedisCacheAdapter" -> RedisCacheAdapter.create();
            default -> throw unsupported(BackendCapability.CACHE);
        };
    }

    @Bean
    EventTransportPort eventTransportPort(AdapterBindings bindings, EventSink eventSink) {
        return switch (bindings.provider(BackendCapability.EVENTS)) {
            case "PostgresOutboxTransportAdapter" -> new PostgresOutboxTransportAdapter(eventSink);
            case "KafkaEventTransportAdapter" -> KafkaEventTransportAdapter.create();
            default -> throw unsupported(BackendCapability.EVENTS);
        };
    }

    @Bean
    ObjectStorePort objectStorePort(AdapterBindings bindings, @Value("${credit.objects.root}") Path root) {
        return switch (bindings.provider(BackendCapability.OBJECTS)) {
            case "VersionedFilesystemObjectAdapter" -> new VersionedFilesystemObjectAdapter(root);
            case "S3ObjectStoreAdapter" -> S3ObjectStoreAdapter.create();
            default -> throw unsupported(BackendCapability.OBJECTS);
        };
    }

    private static InvalidAdapterBindingException unsupported(BackendCapability capability) {
        return new InvalidAdapterBindingException("Unsupported provider for " + capability.key());
    }
}
