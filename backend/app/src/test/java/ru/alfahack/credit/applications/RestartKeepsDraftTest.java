package ru.alfahack.credit.applications;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

import org.junit.jupiter.api.Test;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.context.ConfigurableApplicationContext;

import ru.alfahack.credit.CreditApplication;
import ru.alfahack.credit.access.application.AuthenticatedSession;
import ru.alfahack.credit.applications.application.ApplicationCommands;
import ru.alfahack.credit.applications.application.ApplicationService;
import ru.alfahack.credit.applications.application.ApplicationView;
import ru.alfahack.credit.support.EmbeddedPostgresConfiguration;

/** P05 «restart keeps draft»: черновик, сохранённый до остановки приложения, читается после нового запуска. */
class RestartKeepsDraftTest {

    static ConfigurableApplicationContext start() {
        return new SpringApplicationBuilder(CreditApplication.class, EmbeddedPostgresConfiguration.class)
                .web(WebApplicationType.NONE)
                .profiles("demo")
                .run("--spring.datasource.password=unused", "--credit.scheduling.enabled=false",
                        "--credit.objects.root=" + System.getProperty("java.io.tmpdir") + "/credit-test-objects");
    }

    static AuthenticatedSession representativeA() {
        return new AuthenticatedSession("restart-test", "representative-a", "company-a", 1, "csrf",
                Instant.now().plusSeconds(3600), 1, Map.of("company-a", Set.of("REPRESENTATIVE")));
    }

    @Test
    void draftSurvivesRestart() {
        String applicationId;
        try (ConfigurableApplicationContext first = start()) {
            ApplicationService service = first.getBean(ApplicationService.class);
            ApplicationView created = service.create(representativeA(), "restart-" + UUID.randomUUID(),
                    new ApplicationCommands.Create(
                            "company-a", "credit-line", 1, "Пополнение склада", 40_000_000, 12, null)).application();
            ApplicationView saved = service.patch(representativeA(), created.applicationId(), 1,
                    new ApplicationCommands.Patch(null, null, 24, null, null));
            assertThat(saved.version()).isEqualTo(2);
            applicationId = created.applicationId();
        }

        try (ConfigurableApplicationContext second = start()) {
            ApplicationView reloaded = second.getBean(ApplicationService.class).get(representativeA(), applicationId);

            assertThat(reloaded.status()).isEqualTo("DRAFT");
            assertThat(reloaded.version()).isEqualTo(2);
            assertThat(reloaded.termMonths()).isEqualTo(24);
            assertThat(reloaded.purpose()).isEqualTo("Пополнение склада");
        }
    }
}
