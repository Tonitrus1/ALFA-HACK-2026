package ru.alfahack.credit.access.api;

import java.util.List;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;

/**
 * credit.demo.* — demo-вход синтетическими аккаунтами. По умолчанию выключен: маршруты /demo/** дают 404.
 * Включается только в локальном профиле demo с синтетикой.
 */
@ConfigurationProperties("credit.demo")
record DemoProperties(@DefaultValue("false") boolean enabled, @DefaultValue List<String> allowedOrigins) {
}
