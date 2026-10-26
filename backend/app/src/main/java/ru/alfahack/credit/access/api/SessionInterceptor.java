package ru.alfahack.credit.access.api;

import java.util.Set;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import org.springframework.web.servlet.HandlerInterceptor;

import ru.alfahack.credit.access.application.AuthenticatedSession;
import ru.alfahack.credit.access.application.SessionService;
import ru.alfahack.credit.platform.web.ApplicationException;
import ru.alfahack.credit.platform.web.ErrorKind;

/**
 * Для /api/v1/**: требует действующую сессию (401), CSRF-токен на изменяющих методах (403)
 * и совпадение X-Company-Context с contextVersion до любого эффекта (409).
 */
class SessionInterceptor implements HandlerInterceptor {

    static final String ATTRIBUTE = AuthenticatedSession.class.getName();
    static final String CSRF_HEADER = "X-CSRF-Token";
    static final String COMPANY_CONTEXT_HEADER = "X-Company-Context";

    private static final Set<String> SAFE_METHODS = Set.of("GET", "HEAD", "OPTIONS");

    private final SessionService sessions;

    SessionInterceptor(SessionService sessions) {
        this.sessions = sessions;
    }

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) {
        if (request.getMethod().equals("POST") && request.getRequestURI().equals("/api/v1/auth/login")) return true;
        AuthenticatedSession session = SessionCookies.read(request)
                .flatMap(sessions::authenticate)
                .orElseThrow(() -> new ApplicationException(
                        ErrorKind.UNAUTHENTICATED, "UNAUTHENTICATED", "Требуется вход"));

        if (!SAFE_METHODS.contains(request.getMethod())
                && !sessions.csrfMatches(session, request.getHeader(CSRF_HEADER))) {
            throw new ApplicationException(ErrorKind.FORBIDDEN, "CSRF_TOKEN_INVALID", "Не удалось подтвердить безопасность действия. Обновите страницу и повторите попытку");
        }

        String companyContext = request.getHeader(COMPANY_CONTEXT_HEADER);
        if (companyContext != null && !companyContext.equals(Long.toString(session.contextVersion()))) {
            throw SessionService.contextChanged();
        }

        request.setAttribute(ATTRIBUTE, session);
        return true;
    }
}
