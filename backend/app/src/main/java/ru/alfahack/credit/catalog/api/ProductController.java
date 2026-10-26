package ru.alfahack.credit.catalog.api;

import java.util.List;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Size;

import com.fasterxml.jackson.annotation.JsonInclude;

import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import ru.alfahack.credit.access.application.AuthenticatedSession;
import ru.alfahack.credit.access.application.CompanyAccessService;
import ru.alfahack.credit.catalog.application.CatalogService;
import ru.alfahack.credit.catalog.application.ProductView;
import ru.alfahack.credit.platform.support.Money;

@RestController
@Validated
class ProductController {

    @JsonInclude(JsonInclude.Include.NON_NULL)
    record Product(
            String productId,
            long version,
            String name,
            String purpose,
            Money minAmount,
            Money maxAmount,
            long minMonths,
            long maxMonths,
            String preliminaryDisclosure) {

        static Product of(ProductView view) {
            return new Product(
                    view.productId(), view.version(), view.name(), view.purpose(),
                    Money.rub(view.minAmountMinor()), Money.rub(view.maxAmountMinor()),
                    view.minMonths(), view.maxMonths(), view.preliminaryDisclosure());
        }
    }

    @JsonInclude(JsonInclude.Include.NON_NULL)
    record ProductList(List<Product> items, String nextCursor) {
    }

    private final CatalogService catalog;
    private final CompanyAccessService companies;

    ProductController(CatalogService catalog, CompanyAccessService companies) {
        this.catalog = catalog;
        this.companies = companies;
    }

    @GetMapping("/api/v1/products")
    ProductList list(
            AuthenticatedSession session,
            @RequestHeader("X-Company-Context") long companyContext,
            @RequestParam String companyId,
            @RequestParam(required = false) @Size(max = 2048) String cursor,
            @RequestParam(defaultValue = "20") @Min(1) @Max(100) int limit) {
        companies.requireSelectedCompany(session, companyId);
        CatalogService.ProductPage page = catalog.listActive(cursor, limit);
        return new ProductList(page.items().stream().map(Product::of).toList(), page.nextCursor());
    }
}
