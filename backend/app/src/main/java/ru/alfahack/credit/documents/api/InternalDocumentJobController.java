package ru.alfahack.credit.documents.api;

import java.time.Instant;
import java.util.List;
import java.util.Set;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import ru.alfahack.credit.documents.application.DocumentJobService;
import ru.alfahack.credit.documents.application.ExtractionView;
import ru.alfahack.credit.documents.application.JobCommands;
import ru.alfahack.credit.platform.web.ApplicationException;
import ru.alfahack.credit.platform.web.ErrorKind;
import ru.alfahack.credit.platform.web.ServiceRoles;

/** Внутренний API заданий (internal.openapi): file-scanner — SCAN, document-ocr — EXTRACT. */
@RestController
@Validated
@RequestMapping("/internal/v1/document-jobs")
class InternalDocumentJobController {

    static final String SCANNER = "file-scanner";
    static final String OCR = "document-ocr";
    static final long MAX = 9007199254740991L;

    record JobClaim(@NotBlank @Size(max = 256) String workerId, @NotNull @Pattern(regexp = "SCAN|EXTRACT") String jobType) {
    }

    record LeaseRenewal(
            @NotBlank @Size(max = 256) String workerId,
            @NotNull @Min(1) @Max(MAX) Long generation,
            @NotBlank @Size(max = 256) String leaseToken) {
    }

    record ScanResult(
            @NotNull @Min(1) @Max(MAX) Long generation,
            @NotBlank @Size(max = 256) String objectVersion,
            @NotNull @Pattern(regexp = "CLEAN|REJECTED|ERROR") String verdict,
            @NotBlank @Size(max = 256) String engineVersion,
            @Size(min = 1, max = 256) String cleanObjectRef,
            @NotBlank @Size(max = 256) String workerId,
            @NotBlank @Size(max = 256) String leaseToken) {
    }

    record ExtractionField(
            @NotBlank @Size(max = 256) String name,
            @NotNull @Size(max = 2000) String value,
            @NotNull @DecimalMin("0") @DecimalMax("1") Double confidence,
            @NotNull @Min(1) @Max(MAX) Integer page) {
    }

    record ExtractionResult(
            @NotNull @Min(1) @Max(MAX) Long generation,
            @NotBlank @Size(max = 256) String objectVersion,
            @NotBlank @Size(max = 256) String engineVersion,
            @NotNull @Pattern(regexp = "READY|FAILED") String status,
            @NotNull @Size(max = 100) List<@NotNull @Valid ExtractionField> fields,
            @NotBlank @Size(max = 256) String workerId,
            @NotBlank @Size(max = 256) String leaseToken) {
    }

    record JobLease(
            String jobId, long generation, Instant leaseUntil, String documentId, String objectVersion,
            String objectRef, String jobType, String leaseToken) {

        static JobLease of(JobCommands.JobLease lease) {
            return new JobLease(lease.jobId(), lease.generation(), lease.leaseUntil(), lease.documentId(),
                    lease.objectVersion(), lease.objectRef(), lease.jobType(), lease.leaseToken());
        }
    }

    record Receipt(String receiptId, Instant recordedAt) {
    }

    private final DocumentJobService jobs;

    InternalDocumentJobController(DocumentJobService jobs) {
        this.jobs = jobs;
    }

    @PostMapping(path = "/claim", consumes = "application/json")
    ResponseEntity<JobLease> claim(HttpServletRequest request, @Valid @RequestBody JobClaim body) {
        requireRoleFor(request, body.jobType());
        return jobs.claim(body.workerId(), body.jobType())
                .map(lease -> ResponseEntity.ok(JobLease.of(lease)))
                .orElseGet(() -> ResponseEntity.noContent().build());
    }

    @PostMapping(path = "/{jobId}/renew", consumes = "application/json")
    JobLease renew(HttpServletRequest request, @PathVariable String jobId, @Valid @RequestBody LeaseRenewal body) {
        String role = ServiceRoles.require(request, Set.of(SCANNER, OCR));
        String jobType = SCANNER.equals(role) ? DocumentJobService.SCAN : DocumentJobService.EXTRACT;
        return JobLease.of(jobs.renew(jobId, jobType,
                new JobCommands.LeaseProof(body.workerId(), body.generation(), body.leaseToken())));
    }

    @PostMapping(path = "/{jobId}/scan-result", consumes = "application/json")
    Receipt scanResult(HttpServletRequest request, @PathVariable String jobId, @Valid @RequestBody ScanResult body) {
        ServiceRoles.require(request, Set.of(SCANNER));
        if ("CLEAN".equals(body.verdict()) != (body.cleanObjectRef() != null)) {
            throw new ApplicationException(ErrorKind.INVALID_REQUEST, "INVALID_REQUEST",
                    "cleanObjectRef обязателен только для CLEAN");
        }
        JobCommands.Receipt receipt = jobs.recordScan(jobId, new JobCommands.ScanResult(
                new JobCommands.LeaseProof(body.workerId(), body.generation(), body.leaseToken()),
                body.objectVersion(), body.verdict(), body.engineVersion(), body.cleanObjectRef()));
        return new Receipt(receipt.receiptId(), receipt.recordedAt());
    }

    @PostMapping(path = "/{jobId}/extraction-result", consumes = "application/json")
    Receipt extractionResult(
            HttpServletRequest request, @PathVariable String jobId, @Valid @RequestBody ExtractionResult body) {
        ServiceRoles.require(request, Set.of(OCR));
        JobCommands.Receipt receipt = jobs.recordExtraction(jobId, new JobCommands.ExtractionResult(
                new JobCommands.LeaseProof(body.workerId(), body.generation(), body.leaseToken()),
                body.objectVersion(), body.engineVersion(), body.status(),
                body.fields().stream()
                        .map(field -> new ExtractionView.Field(field.name(), field.value(), field.confidence(),
                                field.page()))
                        .toList()));
        return new Receipt(receipt.receiptId(), receipt.recordedAt());
    }

    private static void requireRoleFor(HttpServletRequest request, String jobType) {
        ServiceRoles.require(request, Set.of(DocumentJobService.SCAN.equals(jobType) ? SCANNER : OCR));
    }
}
