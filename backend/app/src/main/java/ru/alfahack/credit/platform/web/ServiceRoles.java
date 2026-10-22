package ru.alfahack.credit.platform.web;

import java.util.Set;

import jakarta.servlet.http.HttpServletRequest;

/** Проверка служебной роли внутреннего вызова (x-allowed-service-role контракта). */
public final class ServiceRoles {

    static final String ATTRIBUTE = ServiceRoles.class.getName() + ".role";

    private ServiceRoles() {
    }

    public static String require(HttpServletRequest request, Set<String> allowed) {
        Object role = request.getAttribute(ATTRIBUTE);
        if (!(role instanceof String name) || !allowed.contains(name)) {
            throw new ApplicationException(ErrorKind.FORBIDDEN, "SERVICE_ROLE_FORBIDDEN", "Роль службы не допущена");
        }
        return name;
    }
}
