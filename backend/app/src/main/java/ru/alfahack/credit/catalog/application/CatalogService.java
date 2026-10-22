package ru.alfahack.credit.catalog.application;

import java.util.List;
import java.util.Optional;

import org.springframework.stereotype.Service;

import ru.alfahack.credit.catalog.infrastructure.ProductRepository;

/** Версионированный каталог продуктов. */
@Service
public class CatalogService {

    public record ProductPage(List<ProductView> items, String nextCursor) {
    }

    private final ProductRepository products;

    public CatalogService(ProductRepository products) {
        this.products = products;
    }

    public ProductPage listActive(String cursor, int limit) {
        List<ProductView> rows = products.listActive(cursor, limit + 1);
        if (rows.size() <= limit) {
            return new ProductPage(rows, null);
        }
        List<ProductView> page = List.copyOf(rows.subList(0, limit));
        ProductView last = page.getLast();
        return new ProductPage(page, last.productId());
    }

    /** Точная версия продукта; неактивная тоже возвращается — решение о допустимости за вызывающим. */
    public Optional<ProductView> find(String productId, long version) {
        return products.find(productId, version);
    }
}
