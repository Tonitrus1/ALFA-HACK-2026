package ru.alfahack.credit.access.api;

import java.time.Clock;
import java.util.List;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import ru.alfahack.credit.access.application.ActorView;
import ru.alfahack.credit.access.application.IssuedSession;
import ru.alfahack.credit.access.application.SessionProperties;
import ru.alfahack.credit.access.application.SessionService;
import ru.alfahack.credit.platform.web.ApplicationException;
import ru.alfahack.credit.platform.web.ErrorKind;

/**
 * Demo-вход синтетическим представителем (demo.openapi: G01). Существует только при credit.demo.enabled=true.
 * Проверяет точный Origin и JSON Content-Type. Оператор имитатора здесь не входит.
 */
@RestController
@ConditionalOnProperty(name = "credit.demo.enabled", havingValue = "true")
@RequestMapping("/demo/api/v1")
class DemoAccessController {

    record DemoAccount(String accountId, String displayName) {
    }

    record DemoAccountList(List<DemoAccount> items) {
    }

    private final SessionService sessions;
    private final SessionProperties sessionProperties;
    private final DemoProperties demoProperties;
    private final Clock clock;

    DemoAccessController(
            SessionService sessions, SessionProperties sessionProperties, DemoProperties demoProperties, Clock clock) {
        this.sessions = sessions;
        this.sessionProperties = sessionProperties;
        this.demoProperties = demoProperties;
        this.clock = clock;
    }

    @GetMapping("/accounts")
    DemoAccountList accounts() {
        return new DemoAccountList(sessions.demoAccounts().stream()
                .map(actor -> new DemoAccount(actor.actorId(), actor.displayName()))
                .toList());
    }

    @PostMapping(path = "/session", consumes = "application/json")
    ResponseEntity<SessionResponse> login(
            HttpServletRequest request,
            @RequestHeader(name = HttpHeaders.ORIGIN, required = false) String origin,
            @Valid @RequestBody DemoLoginRequest body) {
        if (origin == null || !demoProperties.allowedOrigins().contains(origin)) {
            throw new ApplicationException(ErrorKind.FORBIDDEN, "ORIGIN_NOT_ALLOWED", "Недопустимый источник запроса");
        }
        IssuedSession issued = sessions.loginRepresentative(body.accountId(), SessionCookies.read(request));
        String displayName = sessions.actor(issued.session().actorId()).map(ActorView::displayName).orElse(null);
        return ResponseEntity.ok()
                .header(HttpHeaders.SET_COOKIE, SessionCookies.issue(
                        issued.token(), issued.session().expiresAt(), clock.instant(), sessionProperties.cookieSecure())
                        .toString())
                .body(SessionResponse.of(issued.session(), displayName));
    }
}
