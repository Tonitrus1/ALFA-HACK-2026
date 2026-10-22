package ru.alfahack.credit.platform.bindings;

import java.util.Map;

import org.springframework.boot.context.properties.ConfigurationProperties;

/** credit.adapters.* — привязки backend-способностей к провайдерам. */
@ConfigurationProperties("credit.adapters")
public record AdapterBindingsProperties(
        String profile,
        boolean automaticProviderFallback,
        Map<String, String> bindings) {
}
