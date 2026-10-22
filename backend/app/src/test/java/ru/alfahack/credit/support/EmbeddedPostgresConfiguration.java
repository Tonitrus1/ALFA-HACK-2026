package ru.alfahack.credit.support;

import java.io.IOException;
import java.io.UncheckedIOException;

import javax.sql.DataSource;

import io.zonky.test.db.postgres.embedded.EmbeddedPostgres;

import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;

/** Один встроенный PostgreSQL 17.11 на JVM тестов; Docker не нужен. */
@TestConfiguration(proxyBeanMethods = false)
public class EmbeddedPostgresConfiguration {

    private static EmbeddedPostgres postgres;

    static synchronized EmbeddedPostgres postgres() {
        if (postgres == null) {
            try {
                postgres = EmbeddedPostgres.builder().start();
            } catch (IOException e) {
                throw new UncheckedIOException(e);
            }
        }
        return postgres;
    }

    @Bean
    DataSource dataSource() {
        return postgres().getPostgresDatabase();
    }
}
