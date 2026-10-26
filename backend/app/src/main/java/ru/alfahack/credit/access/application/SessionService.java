package ru.alfahack.credit.access.application;

import java.time.Clock;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.function.Supplier;

import org.springframework.stereotype.Service;

import ru.alfahack.credit.access.infrastructure.AccessRepository;
import ru.alfahack.credit.platform.web.ApplicationException;
import ru.alfahack.credit.platform.web.ErrorKind;
import ru.alfahack.credit.ports.PortErrorClass;
import ru.alfahack.credit.ports.PortException;
import ru.alfahack.credit.ports.sessions.CompanyMembership;
import ru.alfahack.credit.ports.sessions.NewSession;
import ru.alfahack.credit.ports.sessions.Session;
import ru.alfahack.credit.ports.sessions.SessionLookup;
import ru.alfahack.credit.ports.sessions.SessionStorePort;

/** Вход, проверка и смена компании серверной сессии. Отказ хранилища закрывает доступ. */
@Service
public class SessionService {

    public static final String COMPANY_CONTEXT_CHANGED = "COMPANY_CONTEXT_CHANGED";

    private final SessionStorePort sessions;
    private final AccessRepository repository;
    private final SessionProperties properties;
    private final Clock clock;

    public SessionService(
            SessionStorePort sessions, AccessRepository repository, SessionProperties properties, Clock clock) {
        this.sessions = sessions;
        this.repository = repository;
        this.properties = properties;
        this.clock = clock;
    }

    public Optional<ActorView> actor(String actorId) {
        return repository.findActor(actorId);
    }

    /** Синтетические представители для demo-входа; оператор сюда не входит. */
    public List<ActorView> demoAccounts() {
        return repository.listActiveRepresentatives();
    }

    /**
     * Вход представителя. Если компания одна, она выбирается сразу. Предыдущая сессия браузера отзывается.
     */
    public IssuedSession loginRepresentative(String accountId, Optional<String> previousToken) {
        ActorView actor = repository.findActor(accountId)
                .filter(ActorView::isActiveRepresentative)
                .orElseThrow(() -> new ApplicationException(ErrorKind.NOT_FOUND, "ACCOUNT_NOT_FOUND", "Аккаунт не найден"));
        previousToken.flatMap(this::authenticate).ifPresent(this::revokeQuietly);

        List<String> companies = repository.companiesOf(actor.actorId(), null, 2).stream()
                .map(CompanyView::companyId)
                .toList();
        String token = SessionTokens.newToken();
        Instant now = clock.instant();
        Session session = call(() -> sessions.issue(new NewSession(
                SessionTokens.hash(token),
                actor.actorId(),
                companies.size() == 1 ? companies.getFirst() : null,
                SessionTokens.newToken(),
                now,
                now.plus(properties.ttl()))));
        return new IssuedSession(token, toAuthenticated(session));
    }

    public Optional<AuthenticatedSession> authenticate(String token) {
        if (token == null || token.isBlank() || token.length() > 256) {
            return Optional.empty();
        }
        SessionLookup lookup = call(() -> sessions.resolve(SessionTokens.hash(token), clock.instant()));
        return lookup instanceof SessionLookup.Found found
                ? Optional.of(toAuthenticated(found.session()))
                : Optional.empty();
    }

    public boolean csrfMatches(AuthenticatedSession session, String csrfToken) {
        return SessionTokens.constantTimeEquals(session.csrfToken(), csrfToken);
    }

    /**
     * Смена компании с повторной проверкой членства. Чужая или несуществующая компания неотличимы (404).
     */
    public AuthenticatedSession selectCompany(AuthenticatedSession session, String companyId) {
        if (!session.isMemberOf(companyId)) {
            throw ApplicationException.notFound();
        }
        try {
            Session updated = sessions.selectCompany(
                    session.sessionHash(), session.version(), companyId, SessionTokens.newToken(), clock.instant());
            return toAuthenticated(updated);
        } catch (PortException e) {
            if (e.errorClass() == PortErrorClass.VERSION_CONFLICT) {
                throw contextChanged();
            }
            throw unavailable(e);
        }
    }

    public static ApplicationException contextChanged() {
        return new ApplicationException(ErrorKind.CONFLICT, COMPANY_CONTEXT_CHANGED, "Компания в сессии изменилась");
    }

    public void logout(AuthenticatedSession session) { revokeQuietly(session); }

    private void revokeQuietly(AuthenticatedSession previous) {
        try {
            sessions.revoke(previous.sessionHash(), previous.version());
        } catch (PortException e) {
            if (e.errorClass() != PortErrorClass.VERSION_CONFLICT) {
                throw unavailable(e);
            }
        }
    }

    private static AuthenticatedSession toAuthenticated(Session session) {
        Map<String, Set<String>> roles = new LinkedHashMap<>();
        for (CompanyMembership membership : session.companyMemberships()) {
            roles.computeIfAbsent(membership.companyId(), key -> new LinkedHashSet<>()).add(membership.role());
        }
        return new AuthenticatedSession(
                session.sessionHash(),
                session.actorId(),
                session.selectedCompanyId(),
                session.contextVersion(),
                session.csrfToken(),
                session.expiresAt(),
                session.version(),
                roles);
    }

    private static <T> T call(Supplier<T> action) {
        try {
            return action.get();
        } catch (PortException e) {
            throw unavailable(e);
        }
    }

    private static ApplicationException unavailable(PortException e) {
        if (e.errorClass() == PortErrorClass.NOT_FOUND) {
            return new ApplicationException(ErrorKind.NOT_FOUND, "ACCOUNT_NOT_FOUND", "Аккаунт не найден");
        }
        return new ApplicationException(ErrorKind.UNAVAILABLE, "SESSION_STORE_UNAVAILABLE", "Сервис временно недоступен");
    }
}
