package ru.alfahack.credit.platform.web;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Map;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import org.springframework.web.servlet.HandlerInterceptor;

/** /internal/**: X-Service-Token сопоставляется с ролью; без совпадения — 401. Роль кладётся в атрибут запроса. */
class ServiceIdentityInterceptor implements HandlerInterceptor {

    static final String HEADER = "X-Service-Token";

    private final ServiceIdentityProperties properties;

    ServiceIdentityInterceptor(ServiceIdentityProperties properties) {
        this.properties = properties;
    }

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) {
        String presented = request.getHeader(HEADER);
        String role = null;
        if (presented != null && !presented.isBlank()) {
            for (Map.Entry<String, String> entry : properties.serviceTokens().entrySet()) {
                String expected = entry.getValue();
                if (expected != null && expected.length() >= 32 && MessageDigest.isEqual(
                        expected.getBytes(StandardCharsets.UTF_8), presented.getBytes(StandardCharsets.UTF_8))) {
                    role = entry.getKey();
                }
            }
        }
        if (role == null) {
            throw new ApplicationException(ErrorKind.UNAUTHENTICATED, "SERVICE_UNAUTHENTICATED", "Неизвестная служба");
        }
        request.setAttribute(ServiceRoles.ATTRIBUTE, role);
        return true;
    }
}
