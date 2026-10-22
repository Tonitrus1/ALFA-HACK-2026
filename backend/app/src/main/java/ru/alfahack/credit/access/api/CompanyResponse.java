package ru.alfahack.credit.access.api;

import java.time.Instant;
import java.util.List;

import com.fasterxml.jackson.annotation.JsonInclude;

import ru.alfahack.credit.access.application.CompanyView;

/** Схемы Company и CompanyList публичного контракта. */
@JsonInclude(JsonInclude.Include.NON_NULL)
record CompanyResponse(
        String companyId, String displayName, String taxId, List<String> roles, Instant sourceUpdatedAt) {

    static CompanyResponse of(CompanyView company) {
        return new CompanyResponse(
                company.companyId(), company.displayName(), company.taxId(), company.roles(), company.sourceUpdatedAt());
    }

    @JsonInclude(JsonInclude.Include.NON_NULL)
    record Page(List<CompanyResponse> items, String nextCursor) {
    }
}
