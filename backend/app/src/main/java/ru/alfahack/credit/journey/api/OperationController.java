package ru.alfahack.credit.journey.api;

import java.time.Instant;

import com.fasterxml.jackson.annotation.JsonInclude;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RestController;

import ru.alfahack.credit.access.application.AuthenticatedSession;
import ru.alfahack.credit.access.application.CompanyAccessService;
import ru.alfahack.credit.journey.application.CommandOperations;
import ru.alfahack.credit.journey.application.OperationView;
import ru.alfahack.credit.platform.web.ApplicationException;

@RestController
class OperationController {

    /** Схема Operation публичного контракта. */
    @JsonInclude(JsonInclude.Include.NON_NULL)
    record Operation(
            String operationId,
            String status,
            String applicationId,
            Instant updatedAt,
            String safeMessage,
            String operationType,
            String resultCode,
            Integer retryAfterSeconds,
            String resourceId,
            String companyId,
            Instant createdAt) {

        static Operation of(OperationView view) {
            boolean open = "PENDING".equals(view.state()) || "RECONCILING".equals(view.state());
            return new Operation(
                    view.operationId(), view.state(), view.applicationId(), view.updatedAt(), view.safeMessage(),
                    view.commandType(), view.resultCode(), open ? 1 : null, view.resourceId(), view.companyId(),
                    view.createdAt());
        }
    }

    private final CommandOperations operations;
    private final CompanyAccessService companies;

    OperationController(CommandOperations operations, CompanyAccessService companies) {
        this.operations = operations;
        this.companies = companies;
    }

    @GetMapping("/api/v1/operations/{operationId}")
    Operation get(
            AuthenticatedSession session,
            @RequestHeader("X-Company-Context") long companyContext,
            @PathVariable String operationId) {
        String companyId = companies.selectedCompany(session);
        return operations.findForActor(operationId, session.actorId(), companyId)
                .map(Operation::of)
                .orElseThrow(ApplicationException::notFound);
    }
}
