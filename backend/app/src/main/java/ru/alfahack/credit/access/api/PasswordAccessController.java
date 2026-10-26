package ru.alfahack.credit.access.api;

import java.time.Clock;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import ru.alfahack.credit.access.application.*;
import ru.alfahack.credit.platform.web.ApplicationException;
import ru.alfahack.credit.platform.web.ErrorKind;

@RestController
@RequestMapping("/api/v1/auth")
class PasswordAccessController {
    record Login(@NotBlank @Size(max=128) String login, @NotBlank @Size(max=256) String password) {
        @Override public String toString() { return "Login[credentials redacted]"; }
    }
    private final PasswordLoginService passwords;
    private final SessionService sessions;
    private final SessionProperties properties;
    private final AuthProperties auth;
    private final Clock clock;

    PasswordAccessController(PasswordLoginService passwords, SessionService sessions,
            SessionProperties properties, AuthProperties auth, Clock clock) {
        this.passwords=passwords; this.sessions=sessions; this.properties=properties; this.auth=auth; this.clock=clock;
    }

    @PostMapping(path="/login",consumes="application/json")
    ResponseEntity<SessionResponse> login(HttpServletRequest request,
            @RequestHeader(name=HttpHeaders.ORIGIN,required=false) String origin,
            @Valid @RequestBody Login body) {
        if (origin == null || !auth.allowedOrigins().contains(origin)) {
            throw new ApplicationException(ErrorKind.FORBIDDEN,"ORIGIN_NOT_ALLOWED","Недопустимый источник запроса");
        }
        String actor = passwords.authenticate(body.login(),body.password()).orElseThrow(() ->
                new ApplicationException(ErrorKind.UNAUTHENTICATED,"INVALID_CREDENTIALS",
                        "Неверный логин или пароль. Проверьте данные и попробуйте снова."));
        IssuedSession issued = sessions.loginRepresentative(actor,SessionCookies.read(request));
        String display = sessions.actor(actor).map(ActorView::displayName).orElse(null);
        return ResponseEntity.ok().header(HttpHeaders.SET_COOKIE,
                SessionCookies.issue(issued.token(),issued.session().expiresAt(),clock.instant(),properties.cookieSecure()).toString())
                .body(SessionResponse.of(issued.session(),display));
    }
}
