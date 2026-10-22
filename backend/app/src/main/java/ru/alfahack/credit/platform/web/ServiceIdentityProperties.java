package ru.alfahack.credit.platform.web;

import java.util.Map;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * credit.internal.service-tokens.&lt;role&gt; — высокоэнтропийные секреты служебных ролей local-mvp
 * (X-Service-Token). Пустой или отсутствующий токен отключает роль; секреты задаются только окружением.
 */
@ConfigurationProperties("credit.internal")
public record ServiceIdentityProperties(Map<String, String> serviceTokens) {

    public ServiceIdentityProperties {
        serviceTokens = serviceTokens == null ? Map.of() : Map.copyOf(serviceTokens);
    }
}
