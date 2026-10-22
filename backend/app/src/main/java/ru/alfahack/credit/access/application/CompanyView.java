package ru.alfahack.credit.access.application;

import java.time.Instant;
import java.util.List;

/** Компания с ролями текущего участника. */
public record CompanyView(
        String companyId, String displayName, String taxId, List<String> roles, Instant sourceUpdatedAt) {

    public CompanyView {
        roles = List.copyOf(roles);
    }
}
