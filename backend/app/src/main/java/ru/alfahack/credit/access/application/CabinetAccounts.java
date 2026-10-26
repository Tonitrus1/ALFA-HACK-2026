package ru.alfahack.credit.access.application;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

/** Provision the two project accounts from installation secrets after Flyway has seeded actors. */
@Component
@ConditionalOnProperty(name="credit.demo.enabled", havingValue="true")
public class CabinetAccounts implements ApplicationRunner {
    private final JdbcClient jdbc;
    private final String passwordA;
    private final String passwordB;

    public CabinetAccounts(JdbcClient jdbc,
            @Value("${credit.auth.company-a-password:}") String passwordA,
            @Value("${credit.auth.company-b-password:}") String passwordB) {
        this.jdbc=jdbc; this.passwordA=passwordA; this.passwordB=passwordB;
    }

    @Override
    @Transactional
    public void run(ApplicationArguments args) {
        provision("company-a", "representative-a", passwordA);
        provision("company-b", "representative-b", passwordB);
    }

    private void provision(String login, String actor, String password) {
        if (password.length() < 12 || password.length() > 256) {
            throw new IllegalStateException("Configure CABINET_A_PASSWORD and CABINET_B_PASSWORD (12–256 characters)");
        }
        var previous = jdbc.sql("SELECT password_hash FROM access.credential WHERE login=:login FOR UPDATE")
                .param("login", login).query(String.class).optional();
        if (previous.isPresent() && PasswordHash.matches(password, previous.get())) return;
        jdbc.sql("""
                INSERT INTO access.credential(login,actor_id,password_hash) VALUES(:login,:actor,:hash)
                ON CONFLICT(login) DO UPDATE SET password_hash=excluded.password_hash,
                    failed_attempts=0,locked_until=NULL,updated_at=now()
                """).param("login",login).param("actor",actor).param("hash",PasswordHash.encode(password)).update();
        jdbc.sql("UPDATE access.actor SET auth_epoch=auth_epoch+1 WHERE actor_id=:actor")
                .param("actor",actor).update();
    }
}
