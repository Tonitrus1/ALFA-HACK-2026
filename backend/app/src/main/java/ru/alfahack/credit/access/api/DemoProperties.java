package ru.alfahack.credit.access.api;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;

/**
 * Enables project account provisioning in the local demo profile. Public login always requires a password.
 */
@ConfigurationProperties("credit.demo")
record DemoProperties(@DefaultValue("false") boolean enabled) {
}
