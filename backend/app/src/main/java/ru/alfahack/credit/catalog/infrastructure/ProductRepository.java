package ru.alfahack.credit.catalog.infrastructure;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.List;
import java.util.Optional;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

import ru.alfahack.credit.catalog.application.ProductView;

@Repository
public class ProductRepository {

    private static final String SELECT = """
            SELECT product_id, version, name, purpose, min_amount_minor, max_amount_minor, min_months, max_months,
                   min_business_age_months, financial_required, requirements_version, preliminary_disclosure, active
            FROM catalog.product
            """;

    private final JdbcClient jdbc;

    public ProductRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    /** Активные продукты, последняя версия каждого, keyset по productId. */
    public List<ProductView> listActive(String afterProductId, int limit) {
        return jdbc.sql("""
                        SELECT DISTINCT ON (product_id) product_id, version, name, purpose, min_amount_minor,
                               max_amount_minor, min_months, max_months, min_business_age_months, financial_required,
                               requirements_version, preliminary_disclosure, active
                        FROM catalog.product
                        WHERE active AND (CAST(:after AS text) IS NULL OR product_id > :after)
                        ORDER BY product_id, version DESC
                        LIMIT :limit
                        """)
                .param("after", afterProductId)
                .param("limit", limit)
                .query((rs, row) -> map(rs))
                .list();
    }

    public Optional<ProductView> find(String productId, long version) {
        return jdbc.sql(SELECT + " WHERE product_id = :id AND version = :version")
                .param("id", productId)
                .param("version", version)
                .query((rs, row) -> map(rs))
                .optional();
    }

    private static ProductView map(ResultSet rs) throws SQLException {
        return new ProductView(
                rs.getString("product_id"),
                rs.getLong("version"),
                rs.getString("name"),
                rs.getString("purpose"),
                rs.getLong("min_amount_minor"),
                rs.getLong("max_amount_minor"),
                rs.getInt("min_months"),
                rs.getInt("max_months"),
                rs.getInt("min_business_age_months"),
                rs.getBoolean("financial_required"),
                rs.getLong("requirements_version"),
                rs.getString("preliminary_disclosure"),
                rs.getBoolean("active"));
    }
}
