package ru.alfahack.credit.access.application;

import java.util.Arrays;
import java.util.EnumSet;
import java.util.Optional;
import java.util.Set;

/** Роль участника в компании и разрешённые ей действия. Неизвестная роль прав не даёт. */
public enum CompanyRole {

    REPRESENTATIVE(EnumSet.allOf(CompanyAction.class));

    private final Set<CompanyAction> actions;

    CompanyRole(Set<CompanyAction> actions) {
        this.actions = Set.copyOf(actions);
    }

    public boolean allows(CompanyAction action) {
        return actions.contains(action);
    }

    public static Optional<CompanyRole> parse(String value) {
        return Arrays.stream(values()).filter(role -> role.name().equals(value)).findFirst();
    }
}
