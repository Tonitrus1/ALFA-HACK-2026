package ru.alfahack.credit.applications.api;

import java.net.URI;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Size;

import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import ru.alfahack.credit.access.application.AuthenticatedSession;
import ru.alfahack.credit.applications.api.ApplicationDtos.Application;
import ru.alfahack.credit.applications.api.ApplicationDtos.ApplicationList;
import ru.alfahack.credit.applications.api.ApplicationDtos.CommandReceipt;
import ru.alfahack.credit.applications.api.ApplicationDtos.CreateApplication;
import ru.alfahack.credit.applications.api.ApplicationDtos.DraftPatch;
import ru.alfahack.credit.applications.api.ApplicationDtos.Submit;
import ru.alfahack.credit.applications.application.ApplicationCommands;
import ru.alfahack.credit.applications.application.ApplicationService;
import ru.alfahack.credit.applications.application.ApplicationView;
import ru.alfahack.credit.platform.support.ETags;
import ru.alfahack.credit.platform.support.IdempotencyKeys;
import ru.alfahack.credit.platform.web.ApplicationException;
import ru.alfahack.credit.platform.web.ErrorKind;

@RestController
@Validated
@RequestMapping("/api/v1/applications")
class ApplicationController {

    private static final String COMPANY_CONTEXT = "X-Company-Context";

    private final ApplicationService applications;

    ApplicationController(ApplicationService applications) {
        this.applications = applications;
    }

    @PostMapping(consumes = "application/json")
    ResponseEntity<Application> create(
            AuthenticatedSession session,
            @RequestHeader(COMPANY_CONTEXT) long companyContext,
            @RequestHeader(IdempotencyKeys.HEADER) String idempotencyKey,
            @Valid @RequestBody CreateApplication body) {
        ApplicationService.Created created = applications.create(session, idempotencyKey, body.toCommand());
        ApplicationView view = created.application();
        return ResponseEntity.created(URI.create("/api/v1/applications/" + view.applicationId()))
                .eTag(ETags.of(view.version()))
                .body(Application.of(view));
    }

    @GetMapping
    ApplicationList list(
            AuthenticatedSession session,
            @RequestHeader(COMPANY_CONTEXT) long companyContext,
            @RequestParam String companyId,
            @RequestParam(required = false) @Size(max = 2048) String cursor,
            @RequestParam(defaultValue = "20") @Min(1) @Max(100) int limit) {
        ApplicationService.Page page = applications.list(session, companyId, cursor, limit);
        return new ApplicationList(page.items().stream().map(Application::of).toList(), page.nextCursor());
    }

    @GetMapping("/{applicationId}")
    ResponseEntity<Application> get(
            AuthenticatedSession session,
            @RequestHeader(COMPANY_CONTEXT) long companyContext,
            @PathVariable String applicationId) {
        ApplicationView view = applications.get(session, applicationId);
        return ResponseEntity.ok().eTag(ETags.of(view.version())).body(Application.of(view));
    }

    @PatchMapping(path = "/{applicationId}", consumes = "application/json")
    ResponseEntity<Application> patch(
            AuthenticatedSession session,
            @RequestHeader(COMPANY_CONTEXT) long companyContext,
            @RequestHeader(HttpHeaders.IF_MATCH) String ifMatch,
            @PathVariable String applicationId,
            @Valid @RequestBody DraftPatch body) {
        if (body.isEmpty()) {
            throw new ApplicationException(ErrorKind.INVALID_REQUEST, "INVALID_REQUEST", "Пустое обновление");
        }
        ApplicationView view = applications.patch(session, applicationId, ETags.parseIfMatch(ifMatch), body.toCommand());
        return ResponseEntity.ok().eTag(ETags.of(view.version())).body(Application.of(view));
    }

    @PostMapping(path = "/{applicationId}/submit", consumes = "application/json")
    ResponseEntity<CommandReceipt> submit(
            AuthenticatedSession session,
            @RequestHeader(COMPANY_CONTEXT) long companyContext,
            @RequestHeader(IdempotencyKeys.HEADER) String idempotencyKey,
            @PathVariable String applicationId,
            @Valid @RequestBody Submit body) {
        ApplicationCommands.Receipt receipt =
                applications.submit(session, applicationId, idempotencyKey, body.toCommand());
        CommandReceipt response = CommandReceipt.of(receipt);
        return ResponseEntity.status(HttpStatus.ACCEPTED)
                .location(URI.create(response.statusUrl()))
                .header(HttpHeaders.RETRY_AFTER, "1")
                .body(response);
    }
}
