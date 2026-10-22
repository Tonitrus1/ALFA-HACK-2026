package ru.alfahack.credit.platform.bindings;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.context.ConfigurableApplicationContext;

import ru.alfahack.credit.CreditApplication;
import ru.alfahack.credit.adapters.local.BoundedLocalCacheAdapter;
import ru.alfahack.credit.adapters.local.JdbcSessionAdapter;
import ru.alfahack.credit.adapters.local.PostgresOutboxTransportAdapter;
import ru.alfahack.credit.adapters.local.VersionedFilesystemObjectAdapter;
import ru.alfahack.credit.ports.ProviderNotImplementedException;
import ru.alfahack.credit.ports.cache.CachePort;
import ru.alfahack.credit.ports.events.EventTransportPort;
import ru.alfahack.credit.ports.objects.ObjectStorePort;
import ru.alfahack.credit.ports.sessions.SessionStorePort;
import ru.alfahack.credit.support.EmbeddedPostgresConfiguration;

/** P25: local-mvp собирает локальные адаптеры; неизвестная или неподключённая привязка останавливает запуск. */
class CompositionRootTest {

    static ConfigurableApplicationContext start(String... extra) {
        // Аргументы командной строки, а не default properties: они перекрывают application.yml.
        String[] base = {
                "--spring.datasource.password=unused",
                "--credit.scheduling.enabled=false",
                "--credit.objects.root=" + System.getProperty("java.io.tmpdir") + "/credit-test-objects"};
        String[] properties = new String[base.length + extra.length];
        System.arraycopy(base, 0, properties, 0, base.length);
        System.arraycopy(extra, 0, properties, base.length, extra.length);
        return new SpringApplicationBuilder(CreditApplication.class, EmbeddedPostgresConfiguration.class)
                .web(WebApplicationType.NONE)
                .profiles("demo")
                .run(properties);
    }

    @Test
    void localMvpBindsLocalAdapters() {
        try (ConfigurableApplicationContext context = start()) {
            assertThat(context.getBean(SessionStorePort.class)).isInstanceOf(JdbcSessionAdapter.class);
            assertThat(context.getBean(CachePort.class)).isInstanceOf(BoundedLocalCacheAdapter.class);
            assertThat(context.getBean(EventTransportPort.class)).isInstanceOf(PostgresOutboxTransportAdapter.class);
            assertThat(context.getBean(ObjectStorePort.class)).isInstanceOf(VersionedFilesystemObjectAdapter.class);
        }
    }

    @Test
    void notImplementedProviderStopsStartup() {
        assertThatThrownBy(() -> start("--credit.adapters.bindings.cache=RedisCacheAdapter"))
                .hasRootCauseInstanceOf(ProviderNotImplementedException.class);
        assertThatThrownBy(() -> start("--credit.adapters.bindings.sessions=RedisSessionAdapter"))
                .hasRootCauseInstanceOf(ProviderNotImplementedException.class);
    }

    @Test
    void unknownProviderStopsStartup() {
        assertThatThrownBy(() -> start("--credit.adapters.bindings.objects=FtpObjectAdapter"))
                .hasRootCauseInstanceOf(InvalidAdapterBindingException.class);
    }
}
