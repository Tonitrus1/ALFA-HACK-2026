package ru.alfahack.credit.access.application;

import java.time.Duration;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;

/** credit.session.* — время жизни сессии и атрибуты cookie. */
@ConfigurationProperties("credit.session")
public record SessionProperties(
        @DefaultValue("PT8H") Duration ttl,
        @DefaultValue("true") boolean cookieSecure) {
}
