package ru.alfahack.credit;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;

import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.jdbc.core.JdbcTemplate;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.postgresql.PostgreSQLContainer;

/** Приложение поднимается на PostgreSQL 17.11; повторный запуск миграций безопасен. Без Docker пропускается. */
@SpringBootTest
@Testcontainers(disabledWithoutDocker = true)
class CreditApplicationTest {

    @Container
    @ServiceConnection
    static final PostgreSQLContainer POSTGRES = new PostgreSQLContainer("postgres:17.11");

    @Autowired
    JdbcTemplate jdbc;

    @Autowired
    Flyway flyway;

    @Test
    void createsModuleSchemas() {
        List<String> schemas = jdbc.queryForList(
                "select schema_name from information_schema.schemata", String.class);

        assertThat(schemas).contains(
                "access", "catalog", "applications", "consents", "documents",
                "journey", "integration", "workspace", "ml", "kb");
    }

    @Test
    void migrationsAreSafeToRunTwice() {
        assertThat(flyway.migrate().migrationsExecuted).isZero();
        assertThat(flyway.validateWithResult().validationSuccessful).isTrue();
    }
}
