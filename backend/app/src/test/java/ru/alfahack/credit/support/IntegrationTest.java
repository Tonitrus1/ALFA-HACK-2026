package ru.alfahack.credit.support;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.ActiveProfiles;

/** Приложение целиком на встроенном PostgreSQL с demo-профилем и синтетическим seed. */
@Target(ElementType.TYPE)
@Retention(RetentionPolicy.RUNTIME)
@SpringBootTest(properties = {"spring.datasource.password=unused", "credit.scheduling.enabled=false"})
@AutoConfigureMockMvc
@ActiveProfiles("demo")
@Import(EmbeddedPostgresConfiguration.class)
public @interface IntegrationTest {
}
