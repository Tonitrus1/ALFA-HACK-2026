package ru.alfahack.credit.access.application;

import java.util.List;
import java.util.Optional;

import org.springframework.stereotype.Service;

import ru.alfahack.credit.access.infrastructure.AccessRepository;
import ru.alfahack.credit.platform.web.ApplicationException;
import ru.alfahack.credit.platform.web.ErrorKind;

/**
 * Изоляция компаний: ресурсы чужой компании неотличимы от несуществующих (404),
 * недостаток роли в своей компании — 403.
 */
@Service
public class CompanyAccessService {

    public record CompanyPage(List<CompanyView> items, String nextCursor) {
    }

    private final AccessRepository repository;

    public CompanyAccessService(AccessRepository repository) {
        this.repository = repository;
    }

    public CompanyPage listCompanies(AuthenticatedSession session, String cursor, int limit) {
        List<CompanyView> rows = repository.companiesOf(session.actorId(), cursor, limit + 1);
        if (rows.size() <= limit) {
            return new CompanyPage(rows, null);
        }
        List<CompanyView> page = rows.subList(0, limit);
        return new CompanyPage(List.copyOf(page), page.getLast().companyId());
    }

    public CompanyView getCompany(AuthenticatedSession session, String companyId) {
        return repository.companyOf(session.actorId(), companyId).orElseThrow(ApplicationException::notFound);
    }

    /** companyId пути/тела/ресурса должен совпадать с выбранной компанией сессии. */
    public String requireSelectedCompany(AuthenticatedSession session, String companyId) {
        String selected = session.selectedCompanyId();
        if (selected == null || !selected.equals(companyId) || !session.isMemberOf(companyId)) {
            throw ApplicationException.notFound();
        }
        return selected;
    }

    /** Выбранная компания сессии; без выбора — 409, клиент должен выбрать компанию. */
    public String selectedCompany(AuthenticatedSession session) {
        return Optional.ofNullable(session.selectedCompanyId())
                .filter(session::isMemberOf)
                .orElseThrow(() -> new ApplicationException(
                        ErrorKind.CONFLICT, "COMPANY_NOT_SELECTED", "Компания не выбрана"));
    }

    /**
     * Повторная проверка полномочий по авторитетному источнику непосредственно перед commit команды.
     * Отозванное членство даёт 404, отсутствие роли — 403.
     */
    public void recheckAction(String actorId, String companyId, CompanyAction action) {
        CompanyView company = repository.companyOf(actorId, companyId).orElseThrow(ApplicationException::notFound);
        boolean allowed = company.roles().stream()
                .map(CompanyRole::parse)
                .flatMap(Optional::stream)
                .anyMatch(role -> role.allows(action));
        if (!allowed) {
            throw new ApplicationException(ErrorKind.FORBIDDEN, "ACTION_FORBIDDEN", "Недостаточно полномочий");
        }
    }

    public void requireAction(AuthenticatedSession session, String companyId, CompanyAction action) {
        requireSelectedCompany(session, companyId);
        if (!session.can(companyId, action)) {
            throw new ApplicationException(ErrorKind.FORBIDDEN, "ACTION_FORBIDDEN", "Недостаточно полномочий");
        }
    }
}
