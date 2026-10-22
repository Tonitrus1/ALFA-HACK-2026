package ru.alfahack.credit.access.api;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Size;

import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import ru.alfahack.credit.access.application.AuthenticatedSession;
import ru.alfahack.credit.access.application.CompanyAccessService;

@RestController
@Validated
@RequestMapping("/api/v1/companies")
class CompanyController {

    private final CompanyAccessService companies;

    CompanyController(CompanyAccessService companies) {
        this.companies = companies;
    }

    @GetMapping
    CompanyResponse.Page list(
            AuthenticatedSession session,
            @RequestParam(required = false) @Size(max = 2048) String cursor,
            @RequestParam(defaultValue = "20") @Min(1) @Max(100) int limit) {
        CompanyAccessService.CompanyPage page = companies.listCompanies(session, cursor, limit);
        return new CompanyResponse.Page(
                page.items().stream().map(CompanyResponse::of).toList(), page.nextCursor());
    }

    @GetMapping("/{companyId}")
    CompanyResponse get(AuthenticatedSession session, @PathVariable String companyId) {
        return CompanyResponse.of(companies.getCompany(session, companyId));
    }
}
