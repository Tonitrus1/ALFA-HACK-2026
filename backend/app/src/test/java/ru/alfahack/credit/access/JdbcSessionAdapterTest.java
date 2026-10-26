package ru.alfahack.credit.access;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Duration;
import java.time.Instant;
import java.util.UUID;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.simple.JdbcClient;

import ru.alfahack.credit.adapters.local.JdbcSessionAdapter;
import ru.alfahack.credit.ports.PortErrorClass;
import ru.alfahack.credit.ports.PortException;
import ru.alfahack.credit.ports.sessions.NewSession;
import ru.alfahack.credit.ports.sessions.Session;
import ru.alfahack.credit.ports.sessions.SessionLookup;
import ru.alfahack.credit.ports.sessions.SessionStorePort;
import ru.alfahack.credit.support.IntegrationTest;

/** Контрактные случаи SessionStorePort: expiry, revoke, restart, stale authEpoch, wrong company. */
@IntegrationTest
class JdbcSessionAdapterTest {

    @Autowired
    JdbcClient jdbc;

    @Autowired
    SessionStorePort store;

    static final Instant NOW = Instant.parse("2026-10-22T10:00:00Z");

    String issue(String actorId, String companyId) {
        String hash = sha();
        store.issue(new NewSession(hash, actorId, companyId, "csrf", NOW, NOW.plus(Duration.ofHours(1))));
        return hash;
    }

    @Test
    void expiredSessionIsMissing() {
        String hash = issue("representative-a", "company-a");

        assertThat(store.resolve(hash, NOW.plusSeconds(60))).isInstanceOf(SessionLookup.Found.class);
        assertThat(store.resolve(hash, NOW.plus(Duration.ofHours(2)))).isInstanceOf(SessionLookup.Missing.class);
    }

    @Test
    void revokedSessionIsMissingAndRevokeIsCas() {
        String hash = issue("representative-a", "company-a");

        assertThatThrownBy(() -> store.revoke(hash, 99))
                .isInstanceOf(PortException.class)
                .extracting("errorClass").isEqualTo(PortErrorClass.VERSION_CONFLICT);
        assertThat(store.revoke(hash, 1).version()).isEqualTo(2);
        assertThat(store.resolve(hash, NOW)).isInstanceOf(SessionLookup.Missing.class);
    }

    @Test
    void sessionSurvivesNewAdapterInstance() {
        String hash = issue("representative-a", "company-a");

        SessionLookup lookup = new JdbcSessionAdapter(jdbc).resolve(hash, NOW);

        assertThat(lookup).isInstanceOf(SessionLookup.Found.class);
        Session session = ((SessionLookup.Found) lookup).session();
        assertThat(session.selectedCompanyId()).isEqualTo("company-a");
        assertThat(session.companyMemberships()).extracting("companyId").containsExactly("company-a");
    }

    @Test
    void cannotSelectCompanyWithoutMembership() {
        String hash = issue("representative-a", "company-a");

        assertThatThrownBy(() -> store.selectCompany(hash, 1, "company-b", "csrf-2", NOW))
                .isInstanceOf(PortException.class)
                .extracting("errorClass").isEqualTo(PortErrorClass.VERSION_CONFLICT);
    }

    @Test
    void unknownActorCannotGetSession() {
        assertThatThrownBy(() -> issue("nobody", null))
                .isInstanceOf(PortException.class)
                .extracting("errorClass").isEqualTo(PortErrorClass.NOT_FOUND);
    }

    static String sha() {
        return (UUID.randomUUID().toString() + UUID.randomUUID()).replace("-", "");
    }
}
