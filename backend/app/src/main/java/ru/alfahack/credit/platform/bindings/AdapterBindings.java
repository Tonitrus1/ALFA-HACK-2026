package ru.alfahack.credit.platform.bindings;

import java.util.Collections;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.Map;

/** Проверенный выбор провайдеров backend-способностей. */
public final class AdapterBindings {

    private final AdapterProfile profile;
    private final Map<BackendCapability, String> providers;

    private AdapterBindings(AdapterProfile profile, Map<BackendCapability, String> providers) {
        this.profile = profile;
        this.providers = Collections.unmodifiableMap(providers);
    }

    public static AdapterBindings of(String profile, boolean automaticProviderFallback, Map<String, String> bindings) {
        if (automaticProviderFallback) {
            throw new InvalidAdapterBindingException("automaticProviderFallback must be false");
        }
        Map<String, String> remaining = new HashMap<>(bindings == null ? Map.of() : bindings);
        Map<BackendCapability, String> providers = new EnumMap<>(BackendCapability.class);
        for (BackendCapability capability : BackendCapability.values()) {
            String provider = remaining.remove(capability.key());
            if (provider == null) {
                throw new InvalidAdapterBindingException("Missing binding for capability: " + capability.key());
            }
            if (!capability.providers().contains(provider)) {
                throw new InvalidAdapterBindingException(
                        "Unknown provider for " + capability.key() + ": " + provider);
            }
            providers.put(capability, provider);
        }
        if (!remaining.isEmpty()) {
            throw new InvalidAdapterBindingException("Unknown capabilities: " + remaining.keySet());
        }
        return new AdapterBindings(AdapterProfile.fromId(profile), providers);
    }

    public AdapterProfile profile() {
        return profile;
    }

    public String provider(BackendCapability capability) {
        return providers.get(capability);
    }
}
