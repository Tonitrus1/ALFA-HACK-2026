package ru.alfahack.credit.access.application;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.stream.Collectors;


/**
 * Проверенная серверная сессия текущего запроса. Роли — из авторитетного источника на момент запроса.
 * Другие модули получают её аргументом контроллера и проверяют компанию через {@link CompanyAccessService}.
 */
public record AuthenticatedSession(
        String sessionHash,
        String actorId,
        String selectedCompanyId,
        long contextVersion,
        String csrfToken,
        Instant expiresAt,
        long version,
        Map<String, Set<String>> rolesByCompany) {

    public AuthenticatedSession {
        rolesByCompany = rolesByCompany.entrySet().stream()
                .collect(Collectors.toUnmodifiableMap(Map.Entry::getKey, entry -> Set.copyOf(entry.getValue())));
    }

    public boolean isMemberOf(String companyId) {
        return rolesByCompany.containsKey(companyId);
    }

    public boolean can(String companyId, CompanyAction action) {
        return rolesByCompany.getOrDefault(companyId, Set.of()).stream()
                .map(CompanyRole::parse)
                .flatMap(Optional::stream)
                .anyMatch(role -> role.allows(action));
    }

    public List<String> companyIds() {
        return rolesByCompany.keySet().stream().sorted().toList();
    }
}
