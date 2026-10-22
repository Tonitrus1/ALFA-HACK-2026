package ru.alfahack.credit.applications.api;

import java.net.URI;
import java.time.Instant;
import java.util.List;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import com.fasterxml.jackson.annotation.JsonInclude;

import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import ru.alfahack.credit.access.application.AuthenticatedSession;
import ru.alfahack.credit.applications.api.ApplicationDtos.CommandReceipt;
import ru.alfahack.credit.applications.api.ApplicationDtos.DocumentReference;
import ru.alfahack.credit.applications.api.ApplicationDtos.DraftPatch;
import ru.alfahack.credit.applications.api.FinancialStatementController.FinancialConfirmation;
import ru.alfahack.credit.applications.api.FinancialStatementController.FinancialInput;
import ru.alfahack.credit.applications.api.FinancialStatementController.FinancialStatement;
import ru.alfahack.credit.applications.application.ApplicationCommands;
import ru.alfahack.credit.applications.application.FinancialStatementView;
import ru.alfahack.credit.applications.application.InformationCommands;
import ru.alfahack.credit.applications.application.InformationDraftView;
import ru.alfahack.credit.applications.application.InformationResponseService;
import ru.alfahack.credit.journey.application.InformationRequestView;
import ru.alfahack.credit.platform.support.ETags;
import ru.alfahack.credit.platform.support.IdempotencyKeys;

/** RFI: список запросов, черновик ответа, финансовая форма ответа и сам ответ (202). */
@RestController
@Validated
@RequestMapping("/api/v1/applications/{applicationId}/information-requests")
class InformationRequestController {

    static final long MAX = 9007199254740991L;

    @JsonInclude(JsonInclude.Include.NON_NULL)
    record InformationItem(String itemId, String kind, String label, String reason, boolean required,
                           String fieldPath, String requirementId) {
    }

    @JsonInclude(JsonInclude.Include.NON_NULL)
    record InformationRequest(String requestId, long version, List<InformationItem> items, Instant deadline,
                              String status) {

        static InformationRequest of(InformationRequestView view) {
            return new InformationRequest(view.requestId(), view.version(), view.items().stream()
                    .map(i -> new InformationItem(i.itemId(), i.kind(), i.label(), i.reason(), i.required(),
                            i.fieldPath(), i.requirementId()))
                    .toList(), view.deadline(), view.status());
        }
    }

    record InformationRequestList(List<InformationRequest> items) {
    }

    @JsonInclude(JsonInclude.Include.NON_NULL)
    record InformationDraft(long requestVersion, long draftVersion, List<DocumentReference> documentReferences,
                            long requirementsVersion, Long financialStatementVersion) {
    }

    record InformationDraftPatch(
            @NotNull @Min(1) @Max(MAX) Long requestVersion,
            @Valid DraftPatch amendment,
            @Size(max = 100) List<@Valid DocumentReference> documentReferences,
            @Size(max = 2000) String explanation,
            @NotNull @Min(1) @Max(MAX) Long requirementsVersion) {
    }

    record InformationResponse(
            @NotNull @Min(1) @Max(MAX) Long requestVersion,
            @Valid DraftPatch amendment,
            @NotNull @Size(max = 100) List<String> documentIds,
            @Size(max = 2000) String explanation,
            @NotNull @Size(max = 100) List<@Valid DocumentReference> documentReferences,
            @NotNull @Min(1) @Max(MAX) Long requirementsVersion,
            @NotNull @Min(1) @Max(MAX) Long draftVersion,
            @NotNull @Min(1) @Max(MAX) Long financialStatementVersion) {
    }

    private final InformationResponseService responses;

    InformationRequestController(InformationResponseService responses) {
        this.responses = responses;
    }

    @GetMapping
    InformationRequestList list(AuthenticatedSession session, @RequestHeader("X-Company-Context") long context,
                                @PathVariable String applicationId) {
        return new InformationRequestList(
                responses.list(session, applicationId).stream().map(InformationRequest::of).toList());
    }

    @GetMapping("/{requestId}/draft")
    ResponseEntity<InformationDraft> draft(AuthenticatedSession session,
                                           @RequestHeader("X-Company-Context") long context,
                                           @PathVariable String applicationId, @PathVariable String requestId) {
        return draftResponse(responses.draft(session, applicationId, requestId));
    }

    @PatchMapping(path = "/{requestId}/draft", consumes = "application/json")
    ResponseEntity<InformationDraft> patchDraft(
            AuthenticatedSession session, @RequestHeader("X-Company-Context") long context,
            @RequestHeader(HttpHeaders.IF_MATCH) String ifMatch, @PathVariable String applicationId,
            @PathVariable String requestId, @Valid @RequestBody InformationDraftPatch body) {
        return draftResponse(responses.patchDraft(session, applicationId, requestId, ETags.parseIfMatch(ifMatch),
                new InformationCommands.DraftPatch(body.requestVersion(), body.amendment() != null,
                        references(body.documentReferences()), body.explanation(), body.requirementsVersion())));
    }

    @GetMapping("/{requestId}/draft/financial-statement")
    ResponseEntity<FinancialStatement> financial(
            AuthenticatedSession session, @RequestHeader("X-Company-Context") long context,
            @PathVariable String applicationId, @PathVariable String requestId) {
        return statement(responses.financial(session, applicationId, requestId));
    }

    @PutMapping(path = "/{requestId}/draft/financial-statement", consumes = "application/json")
    ResponseEntity<FinancialStatement> saveFinancial(
            AuthenticatedSession session, @RequestHeader("X-Company-Context") long context,
            @RequestHeader("Idempotency-Key") String key, @RequestHeader(HttpHeaders.IF_MATCH) String ifMatch,
            @PathVariable String applicationId, @PathVariable String requestId,
            @Valid @RequestBody FinancialInput body) {
        return statement(responses.saveFinancial(session, applicationId, requestId, ETags.parseIfMatch(ifMatch), key,
                body.toCommand()));
    }

    @PostMapping(path = "/{requestId}/draft/financial-statement/confirm", consumes = "application/json")
    ResponseEntity<FinancialStatement> confirmFinancial(
            AuthenticatedSession session, @RequestHeader("X-Company-Context") long context,
            @RequestHeader("Idempotency-Key") String key, @RequestHeader(HttpHeaders.IF_MATCH) String ifMatch,
            @PathVariable String applicationId, @PathVariable String requestId,
            @Valid @RequestBody FinancialConfirmation body) {
        return statement(responses.confirmFinancial(session, applicationId, requestId, ETags.parseIfMatch(ifMatch),
                key, body.toCommand()));
    }

    @PostMapping(path = "/{requestId}/responses", consumes = "application/json")
    ResponseEntity<CommandReceipt> respond(
            AuthenticatedSession session, @RequestHeader("X-Company-Context") long context,
            @RequestHeader(IdempotencyKeys.HEADER) String key, @PathVariable String applicationId,
            @PathVariable String requestId, @Valid @RequestBody InformationResponse body) {
        ApplicationCommands.Receipt receipt = responses.respond(session, applicationId, requestId, key,
                new InformationCommands.Response(body.requestVersion(), body.amendment() != null, body.documentIds(),
                        body.explanation(), references(body.documentReferences()), body.requirementsVersion(),
                        body.draftVersion(), body.financialStatementVersion()));
        CommandReceipt response = CommandReceipt.of(receipt);
        return ResponseEntity.status(HttpStatus.ACCEPTED).location(URI.create(response.statusUrl()))
                .header(HttpHeaders.RETRY_AFTER, "1").body(response);
    }

    private ResponseEntity<InformationDraft> draftResponse(InformationDraftView draft) {
        return ResponseEntity.ok().eTag(ETags.of(draft.draftVersion())).body(new InformationDraft(
                draft.requestVersion(), draft.draftVersion(), List.of(), draft.requirementsVersion(),
                responses.draftStatementVersion(draft)));
    }

    private static ResponseEntity<FinancialStatement> statement(FinancialStatementView view) {
        return ResponseEntity.ok().eTag(ETags.of(view.containerVersion())).body(FinancialStatement.of(view));
    }

    private static List<ApplicationCommands.DocumentReference> references(List<DocumentReference> references) {
        return references == null ? List.of() : references.stream()
                .map(ref -> new ApplicationCommands.DocumentReference(ref.documentId(), ref.documentVersion(),
                        ref.objectVersion()))
                .toList();
    }
}
