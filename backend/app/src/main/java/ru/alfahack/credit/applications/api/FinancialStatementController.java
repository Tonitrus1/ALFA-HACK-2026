package ru.alfahack.credit.applications.api;

import java.time.Instant;
import java.time.LocalDate;
import java.util.List;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

import com.fasterxml.jackson.annotation.JsonInclude;

import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import ru.alfahack.credit.access.application.AuthenticatedSession;
import ru.alfahack.credit.applications.application.ApplicationCommands;
import ru.alfahack.credit.applications.application.FinancialCommands;
import ru.alfahack.credit.applications.application.FinancialStatementService;
import ru.alfahack.credit.applications.application.FinancialStatementView;
import ru.alfahack.credit.applications.application.FinancialValues;
import ru.alfahack.credit.platform.support.ETags;

/** Финансовая анкета черновика (MLFinancialInput / MLFinancialStatement / MLFinancialConfirmation). */
@RestController
@Validated
@RequestMapping("/api/v1/applications/{applicationId}/financial-statement")
class FinancialStatementController {

    static final long MAX = 9007199254740991L;

    record DocumentReference(
            @NotBlank @Size(max = 128) String documentId,
            @NotNull @Min(1) @Max(MAX) Long documentVersion,
            @NotBlank @Size(max = 128) String objectVersion) {

        ApplicationCommands.DocumentReference toCommand() {
            return new ApplicationCommands.DocumentReference(documentId, documentVersion, objectVersion);
        }

        static DocumentReference of(ApplicationCommands.DocumentReference reference) {
            return new DocumentReference(
                    reference.documentId(), reference.documentVersion(), reference.objectVersion());
        }
    }

    @JsonInclude(JsonInclude.Include.NON_NULL)
    record Values(
            @Min(0) @Max(MAX) Long totalAssetsMinor,
            @Min(0) @Max(MAX) Long totalLiabilitiesMinor,
            @Min(0) @Max(MAX) Long currentAssetsMinor,
            @Min(0) @Max(MAX) Long currentLiabilitiesMinor,
            @Min(-MAX) @Max(MAX) Long equityMinor,
            @Min(0) @Max(MAX) Long revenueMinor,
            @Min(-MAX) @Max(MAX) Long netProfitMinor,
            @Min(-MAX) @Max(MAX) Long ebitMinor) {

        FinancialValues toValues() {
            return new FinancialValues(totalAssetsMinor, totalLiabilitiesMinor, currentAssetsMinor,
                    currentLiabilitiesMinor, equityMinor, revenueMinor, netProfitMinor, ebitMinor);
        }

        static Values of(FinancialValues values) {
            return new Values(values.totalAssetsMinor(), values.totalLiabilitiesMinor(), values.currentAssetsMinor(),
                    values.currentLiabilitiesMinor(), values.equityMinor(), values.revenueMinor(),
                    values.netProfitMinor(), values.ebitMinor());
        }
    }

    record FinancialInput(
            @NotNull LocalDate periodStart,
            @NotNull LocalDate periodEnd,
            @NotNull @Pattern(regexp = "DEMO") String reportingStandard,
            @NotNull @Pattern(regexp = "RUB") String currency,
            @NotNull @Valid Values values,
            @NotNull @Size(max = 10) List<@NotNull @Valid DocumentReference> sourceDocumentReferences) {

        FinancialCommands.Save toCommand() {
            return new FinancialCommands.Save(periodStart, periodEnd, reportingStandard, currency, values.toValues(),
                    sourceDocumentReferences.stream().map(DocumentReference::toCommand).toList());
        }
    }

    record FinancialConfirmation(
            @NotNull @Min(1) @Max(MAX) Long expectedStatementVersion,
            @NotNull @Size(min = 8, max = 8) List<@NotBlank String> confirmedFieldNames,
            @NotNull @Size(max = 10) List<@NotNull @Valid DocumentReference> documentReferences) {

        FinancialCommands.Confirm toCommand() {
            return new FinancialCommands.Confirm(expectedStatementVersion, confirmedFieldNames,
                    documentReferences.stream().map(DocumentReference::toCommand).toList());
        }
    }

    @JsonInclude(JsonInclude.Include.NON_NULL)
    record Provenance(
            String field, String sourceType, String confirmedBy, Instant confirmedAt, String extractionId,
            String objectVersion) {
    }

    record Statement(
            LocalDate periodStart,
            LocalDate periodEnd,
            String reportingStandard,
            String currency,
            Values values,
            List<DocumentReference> sourceDocumentReferences) {
    }

    record FinancialStatement(
            long statementVersion, long containerVersion, boolean confirmed, Statement statement,
            List<Provenance> provenance) {

        static FinancialStatement of(FinancialStatementView view) {
            return new FinancialStatement(
                    view.statementVersion(), view.containerVersion(), view.confirmed(),
                    new Statement(view.periodStart(), view.periodEnd(), view.reportingStandard(), view.currency(),
                            Values.of(view.values()),
                            view.sourceDocumentReferences().stream().map(DocumentReference::of).toList()),
                    view.provenance().stream()
                            .map(p -> new Provenance(p.field(), p.sourceType(), p.confirmedBy(), p.confirmedAt(),
                                    p.extractionId(), p.objectVersion()))
                            .toList());
        }
    }

    private final FinancialStatementService financials;

    FinancialStatementController(FinancialStatementService financials) {
        this.financials = financials;
    }

    @GetMapping
    ResponseEntity<FinancialStatement> get(
            AuthenticatedSession session,
            @RequestHeader("X-Company-Context") long companyContext,
            @PathVariable String applicationId) {
        return respond(financials.get(session, applicationId));
    }

    @PutMapping(consumes = "application/json")
    ResponseEntity<FinancialStatement> save(
            AuthenticatedSession session,
            @RequestHeader("X-Company-Context") long companyContext,
            @RequestHeader("Idempotency-Key") String idempotencyKey,
            @RequestHeader(HttpHeaders.IF_MATCH) String ifMatch,
            @PathVariable String applicationId,
            @Valid @RequestBody FinancialInput body) {
        return respond(financials.save(
                session, applicationId, ETags.parseIfMatch(ifMatch), idempotencyKey, body.toCommand()));
    }

    @PostMapping(path = "/confirm", consumes = "application/json")
    ResponseEntity<FinancialStatement> confirm(
            AuthenticatedSession session,
            @RequestHeader("X-Company-Context") long companyContext,
            @RequestHeader("Idempotency-Key") String idempotencyKey,
            @RequestHeader(HttpHeaders.IF_MATCH) String ifMatch,
            @PathVariable String applicationId,
            @Valid @RequestBody FinancialConfirmation body) {
        return respond(financials.confirm(
                session, applicationId, ETags.parseIfMatch(ifMatch), idempotencyKey, body.toCommand()));
    }

    private static ResponseEntity<FinancialStatement> respond(FinancialStatementView view) {
        return ResponseEntity.ok().eTag(ETags.of(view.containerVersion())).body(FinancialStatement.of(view));
    }
}
