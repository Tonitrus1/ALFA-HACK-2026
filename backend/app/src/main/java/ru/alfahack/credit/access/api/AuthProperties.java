package ru.alfahack.credit.access.api;

import java.util.List;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;

@ConfigurationProperties("credit.auth")
record AuthProperties(@DefaultValue List<String> allowedOrigins) {}
