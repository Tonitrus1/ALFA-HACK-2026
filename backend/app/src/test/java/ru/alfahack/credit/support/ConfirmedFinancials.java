package ru.alfahack.credit.support;

import java.util.List;
import java.util.Optional;

import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;

import ru.alfahack.credit.applications.application.ApplicationCommands;
import ru.alfahack.credit.applications.application.ApplicationView;
import ru.alfahack.credit.applications.application.SubmissionPrerequisites;
import ru.alfahack.credit.catalog.application.ProductView;

/**
 * Тестовый двойник до P08: финансовая форма версии 1 считается подтверждённой. Документы и согласия
 * по-прежнему проверяются закрыто (пустые списки допустимы).
 */
@TestConfiguration(proxyBeanMethods = false)
public class ConfirmedFinancials {

    public static final long STATEMENT_VERSION = 1;

    @Bean
    @Primary
    SubmissionPrerequisites confirmedFinancials() {
        return new SubmissionPrerequisites() {
            @Override
            public Optional<String> confirmedFinancialSnapshot(ApplicationView application, long version) {
                return version == STATEMENT_VERSION
                        ? Optional.of("fin-snapshot-" + application.applicationId())
                        : Optional.empty();
            }

            @Override
            public boolean documentsClean(
                    ApplicationView application, List<ApplicationCommands.DocumentReference> references) {
                return references.isEmpty();
            }

            @Override
            public boolean consentsValid(ApplicationView application, ProductView product, List<String> consents) {
                return consents.isEmpty();
            }
        };
    }
}
