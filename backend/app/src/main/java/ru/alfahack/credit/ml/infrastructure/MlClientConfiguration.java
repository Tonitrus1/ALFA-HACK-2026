package ru.alfahack.credit.ml.infrastructure;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import ru.alfahack.credit.ml.application.MlClient;

/**
 * credit.ml.mode: contract-double (до готовности моделей) или http (ML-сервис internal v2).
 * Неизвестный режим или http без адреса/секрета останавливает запуск — без тихого переключения на двойник.
 */
@Configuration(proxyBeanMethods = false)
class MlClientConfiguration {

    @Bean
    MlClient mlClient(
            @Value("${credit.ml.mode}") String mode,
            @Value("${credit.ml.base-url:}") String baseUrl,
            @Value("${credit.ml.service-token:}") String serviceToken) {
        return switch (mode) {
            case "contract-double" -> new ContractDoubleMlClient();
            case "http" -> {
                if (baseUrl.isBlank() || serviceToken.length() < 32) {
                    throw new IllegalStateException("credit.ml.base-url and credit.ml.service-token are required");
                }
                yield new HttpMlClient(baseUrl, serviceToken);
            }
            default -> throw new IllegalStateException("Unknown credit.ml.mode: " + mode);
        };
    }
}
