package ru.alfahack.credit.platform.bindings;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.HashMap;
import java.util.Map;

import org.junit.jupiter.api.Test;

class AdapterBindingsTest {

    static Map<String, String> localMvp() {
        return new HashMap<>(Map.of(
                "sessions", "JdbcSessionAdapter",
                "cache", "BoundedLocalCacheAdapter",
                "events", "PostgresOutboxTransportAdapter",
                "objects", "VersionedFilesystemObjectAdapter"));
    }

    @Test
    void acceptsLocalMvpBindings() {
        AdapterBindings bindings = AdapterBindings.of("local-mvp", false, localMvp());

        assertThat(bindings.profile()).isEqualTo(AdapterProfile.LOCAL_MVP);
        assertThat(bindings.provider(BackendCapability.SESSIONS)).isEqualTo("JdbcSessionAdapter");
    }

    @Test
    void unknownProviderFails() {
        Map<String, String> bindings = localMvp();
        bindings.put("cache", "MemcachedAdapter");

        assertThatThrownBy(() -> AdapterBindings.of("local-mvp", false, bindings))
                .isInstanceOf(InvalidAdapterBindingException.class)
                .hasMessageContaining("cache");
    }

    @Test
    void missingCapabilityFails() {
        Map<String, String> bindings = localMvp();
        bindings.remove("sessions");

        assertThatThrownBy(() -> AdapterBindings.of("local-mvp", false, bindings))
                .isInstanceOf(InvalidAdapterBindingException.class)
                .hasMessageContaining("sessions");
    }

    @Test
    void unknownCapabilityFails() {
        Map<String, String> bindings = localMvp();
        bindings.put("search", "ElasticAdapter");

        assertThatThrownBy(() -> AdapterBindings.of("local-mvp", false, bindings))
                .isInstanceOf(InvalidAdapterBindingException.class)
                .hasMessageContaining("search");
    }

    @Test
    void unknownProfileFails() {
        assertThatThrownBy(() -> AdapterBindings.of("prod", false, localMvp()))
                .isInstanceOf(InvalidAdapterBindingException.class);
    }

    @Test
    void automaticFallbackIsForbidden() {
        assertThatThrownBy(() -> AdapterBindings.of("local-mvp", true, localMvp()))
                .isInstanceOf(InvalidAdapterBindingException.class);
    }
}
