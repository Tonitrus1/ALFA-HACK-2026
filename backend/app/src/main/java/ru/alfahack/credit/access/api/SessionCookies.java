package ru.alfahack.credit.access.api;

import java.time.Duration;
import java.time.Instant;
import java.util.Arrays;
import java.util.Optional;

import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;

import org.springframework.http.ResponseCookie;

/** Cookie credit_session: HttpOnly, SameSite=Strict, Path=/. */
final class SessionCookies {

    static final String NAME = "credit_session";

    private SessionCookies() {
    }

    static Optional<String> read(HttpServletRequest request) {
        Cookie[] cookies = request.getCookies();
        if (cookies == null) {
            return Optional.empty();
        }
        return Arrays.stream(cookies)
                .filter(cookie -> NAME.equals(cookie.getName()))
                .map(Cookie::getValue)
                .findFirst();
    }

    static ResponseCookie issue(String token, Instant expiresAt, Instant now, boolean secure) {
        return ResponseCookie.from(NAME, token)
                .httpOnly(true)
                .secure(secure)
                .sameSite("Strict")
                .path("/")
                .maxAge(Duration.between(now, expiresAt))
                .build();
    }
}
