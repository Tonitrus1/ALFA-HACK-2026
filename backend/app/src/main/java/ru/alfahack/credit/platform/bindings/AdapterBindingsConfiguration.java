package ru.alfahack.credit.platform.bindings;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.jdbc.core.simple.JdbcClient;

import ru.alfahack.credit.adapters.kafka.KafkaEventTransportAdapter;
import ru.alfahack.credit.adapters.local.JdbcSessionAdapter;
import ru.alfahack.credit.adapters.redis.RedisCacheAdapter;
import ru.alfahack.credit.adapters.redis.RedisSessionAdapter;
import ru.alfahack.credit.adapters.s3.S3ObjectStoreAdapter;
import ru.alfahack.credit.ports.sessions.SessionStorePort;

/**
 * Composition root: ровно одна реализация на способность по {@link AdapterBindings}.
 * Выбор неподключённого провайдера останавливает запуск. Локальные cache/events/objects — P25.
 */
@Configuration(proxyBeanMethods = false)
class AdapterBindingsConfiguration {

    @Bean
    AdapterBindings adapterBindings(AdapterBindingsProperties properties) {
        AdapterBindings bindings = AdapterBindings.of(
                properties.profile(), properties.automaticProviderFallback(), properties.bindings());
        failFastOnNotImplementedProviders(bindings);
        return bindings;
    }

    @Bean
    SessionStorePort sessionStorePort(AdapterBindings bindings, JdbcClient jdbcClient) {
        return switch (bindings.provider(BackendCapability.SESSIONS)) {
            case "JdbcSessionAdapter" -> new JdbcSessionAdapter(jdbcClient);
            case "RedisSessionAdapter" -> RedisSessionAdapter.create();
            default -> throw new InvalidAdapterBindingException("Unsupported sessions provider");
        };
    }

    private static void failFastOnNotImplementedProviders(AdapterBindings bindings) {
        if ("RedisCacheAdapter".equals(bindings.provider(BackendCapability.CACHE))) {
            RedisCacheAdapter.create();
        }
        if ("KafkaEventTransportAdapter".equals(bindings.provider(BackendCapability.EVENTS))) {
            KafkaEventTransportAdapter.create();
        }
        if ("S3ObjectStoreAdapter".equals(bindings.provider(BackendCapability.OBJECTS))) {
            S3ObjectStoreAdapter.create();
        }
    }
}
