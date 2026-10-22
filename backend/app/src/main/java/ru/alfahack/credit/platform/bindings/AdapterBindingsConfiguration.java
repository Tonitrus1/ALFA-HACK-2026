package ru.alfahack.credit.platform.bindings;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Composition root. Бины портов (SessionStorePort, CachePort, EventTransportPort, ObjectStorePort)
 * создаются здесь по {@link AdapterBindings} в задаче P25.
 */
@Configuration(proxyBeanMethods = false)
class AdapterBindingsConfiguration {

    @Bean
    AdapterBindings adapterBindings(AdapterBindingsProperties properties) {
        return AdapterBindings.of(
                properties.profile(), properties.automaticProviderFallback(), properties.bindings());
    }
}
