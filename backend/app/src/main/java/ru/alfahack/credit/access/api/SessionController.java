package ru.alfahack.credit.access.api;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;

import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import ru.alfahack.credit.access.application.ActorView;
import ru.alfahack.credit.access.application.AuthenticatedSession;
import ru.alfahack.credit.access.application.SessionService;

@RestController
@Validated
@RequestMapping("/api/v1/session")
class SessionController {

    private final SessionService sessions;

    SessionController(SessionService sessions) {
        this.sessions = sessions;
    }

    @GetMapping
    SessionResponse current(AuthenticatedSession session) {
        return SessionResponse.of(session, displayName(session));
    }

    /** X-Company-Context уже сверен с contextVersion в {@link SessionInterceptor}; здесь он обязателен. */
    @PostMapping(path = "/company", consumes = "application/json")
    SessionResponse selectCompany(
            AuthenticatedSession session,
            @RequestHeader(SessionInterceptor.COMPANY_CONTEXT_HEADER) @Min(1) @Max(9007199254740991L) long companyContext,
            @Valid @RequestBody SelectCompanyRequest request) {
        AuthenticatedSession updated = sessions.selectCompany(session, request.companyId());
        return SessionResponse.of(updated, displayName(updated));
    }

    private String displayName(AuthenticatedSession session) {
        return sessions.actor(session.actorId()).map(ActorView::displayName).orElse(null);
    }
}
