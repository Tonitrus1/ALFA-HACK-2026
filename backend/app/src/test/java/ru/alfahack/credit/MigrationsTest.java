package ru.alfahack.credit;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;

import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.core.simple.JdbcClient;

import ru.alfahack.credit.support.IntegrationTest;

/** P03/A35: миграции упорядочены, повторный запуск безопасен, seed не дублируется. */
@IntegrationTest
class MigrationsTest {

    @Autowired
    Flyway flyway;

    @Autowired
    JdbcClient jdbc;

    @Test
    void createsModuleSchemas() {
        List<String> schemas = jdbc.sql("SELECT schema_name FROM information_schema.schemata")
                .query(String.class).list();

        assertThat(schemas).contains(
                "access", "catalog", "applications", "consents", "documents",
                "journey", "integration", "workspace", "ml", "kb");
    }

    @Test
    void migrationsAreSafeToRunTwice() {
        assertThat(flyway.migrate().migrationsExecuted).isZero();
        assertThat(flyway.validateWithResult().validationSuccessful).isTrue();
    }

    @Test
    void reseedDoesNotDuplicateData() throws Exception {
        long actors = count("access.actor");
        long memberships = count("access.company_membership");

        String seed = new ClassPathResource("db/seed/demo/R__demo_access_seed.sql")
                .getContentAsString(java.nio.charset.StandardCharsets.UTF_8);
        jdbc.sql(seed).update();

        assertThat(count("access.actor")).isEqualTo(actors);
        assertThat(count("access.company_membership")).isEqualTo(memberships);
    }

    private long count(String table) {
        return jdbc.sql("SELECT count(*) FROM " + table).query(Long.class).single();
    }
}
