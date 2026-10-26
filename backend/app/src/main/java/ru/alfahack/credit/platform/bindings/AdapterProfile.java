package ru.alfahack.credit.platform.bindings;

import java.util.Arrays;

public enum AdapterProfile {

    LOCAL_MVP("local-mvp"),
    LOCAL_INTEGRATIONS("local-integrations"),
    BANK_TARGET("bank-target");

    private final String id;

    AdapterProfile(String id) {
        this.id = id;
    }

    public String id() {
        return id;
    }

    public static AdapterProfile fromId(String id) {
        return Arrays.stream(values())
                .filter(profile -> profile.id.equals(id))
                .findFirst()
                .orElseThrow(() -> new InvalidAdapterBindingException("Unknown adapter profile: " + id));
    }
}
