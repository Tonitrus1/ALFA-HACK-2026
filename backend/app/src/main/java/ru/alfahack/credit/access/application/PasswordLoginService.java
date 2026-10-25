package ru.alfahack.credit.access.application;

import java.time.Clock;
import java.time.Instant;
import java.time.Duration;
import java.util.Locale;
import java.util.Optional;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

/** Locks a credential while checking it so concurrent failed attempts cannot evade the limit. */
@Service
public class PasswordLoginService {
    private record Credential(String actor, String hash, int failures, Instant lockedUntil) {}
    private final JdbcClient jdbc;
    private final TransactionTemplate transactions;
    private final Clock clock;
    private final String dummyHash = PasswordHash.encode("unused-account-password");

    public PasswordLoginService(JdbcClient jdbc, org.springframework.transaction.PlatformTransactionManager manager, Clock clock) {
        this.jdbc = jdbc;
        this.transactions = new TransactionTemplate(manager);
        this.clock = clock;
    }

    public Optional<String> authenticate(String login, String password) {
        String normalized = login.strip().toLowerCase(Locale.ROOT);
        return transactions.execute(status -> {
            var credential = jdbc.sql("""
                    SELECT c.actor_id, c.password_hash, c.failed_attempts, c.locked_until
                    FROM access.credential c JOIN access.actor a ON a.actor_id=c.actor_id
                    WHERE c.login=:login AND NOT a.disabled AND a.kind='REPRESENTATIVE'
                    FOR UPDATE OF c
                    """).param("login", normalized).query((rs, n) -> new Credential(
                            rs.getString(1), rs.getString(2), rs.getInt(3),
                            rs.getTimestamp(4) == null ? null : rs.getTimestamp(4).toInstant())).optional();
            if (credential.isEmpty()) {
                PasswordHash.matches(password, dummyHash);
                return Optional.<String>empty();
            }
            Credential c = credential.get();
            Instant now = clock.instant();
            if (c.lockedUntil() != null && c.lockedUntil().isAfter(now)) return Optional.<String>empty();
            if (PasswordHash.matches(password, c.hash())) {
                jdbc.sql("UPDATE access.credential SET failed_attempts=0,locked_until=NULL WHERE login=:login")
                        .param("login", normalized).update();
                return Optional.of(c.actor());
            }
            int failures = (c.lockedUntil() == null ? c.failures() : 0) + 1;
            jdbc.sql("UPDATE access.credential SET failed_attempts=:failures,locked_until=:locked WHERE login=:login")
                    .param("failures", failures)
                    .param("locked", failures >= 5 ? java.sql.Timestamp.from(now.plus(Duration.ofMinutes(15))) : null)
                    .param("login", normalized).update();
            return Optional.<String>empty();
        });
    }
}
