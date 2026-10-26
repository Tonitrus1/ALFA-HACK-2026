package ru.alfahack.credit.documents.api;

import java.time.Instant;
import java.util.List;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

import com.fasterxml.jackson.annotation.JsonInclude;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import ru.alfahack.credit.access.application.AuthenticatedSession;
import ru.alfahack.credit.catalog.application.DocumentRequirementView;
import ru.alfahack.credit.documents.application.DocumentCommands;
import ru.alfahack.credit.documents.application.DocumentService;
import ru.alfahack.credit.documents.application.DocumentView;
import ru.alfahack.credit.documents.application.ExtractionView;
import ru.alfahack.credit.platform.support.Digests;
import ru.alfahack.credit.platform.support.IdempotencyKeys;

@RestController
@Validated
class DocumentController {

    static final String CONTEXT = "X-Company-Context";
    static final long MAX = 9007199254740991L;

    record UploadInput(
            @NotBlank @Size(max = 256) String fileName,
            @NotNull @Pattern(regexp = "application/pdf|image/jpeg|image/png") String declaredMimeType,
            @NotNull @Min(1) @Max(10485760) Long sizeBytes,
            @NotBlank @Size(max = 256) String documentType,
            @Size(min = 1, max = 256) String requestId,
            @NotBlank @Size(max = 256) String requirementId,
            @NotNull @Min(1) @Max(MAX) Long requirementsVersion,
            @Size(min = 1, max = 256) String replacesDocumentId,
            @Min(1) @Max(MAX) Long expectedDocumentVersion,
            @Min(1) @Max(MAX) Long requestVersion) {

        DocumentCommands.UploadRequest toCommand() {
            return new DocumentCommands.UploadRequest(fileName, declaredMimeType, sizeBytes, documentType, requestId,
                    requestVersion, requirementId, requirementsVersion, replacesDocumentId, expectedDocumentVersion);
        }
    }

    record UploadIntent(
            String uploadId, String documentId, String uploadUrl, String grant, Instant expiresAt, long maxBytes) {
    }

    record DownloadIntent(String downloadUrl, String grant, Instant expiresAt) {
    }

    @JsonInclude(JsonInclude.Include.NON_NULL)
    record Document(
            String documentId, String applicationId, long version, String fileName, String scanState,
            String extractionState, String extractionId, String companyId, String objectVersion, Long sizeBytes,
            String contentType, String requirementId, String replacesDocumentId) {

        static Document of(DocumentView view) {
            return new Document(view.documentId(), view.applicationId(), view.version(), view.fileName(),
                    view.scanState(), view.extractionState(), view.extractionId(), view.companyId(),
                    view.objectVersion(), view.sizeBytes(),
                    view.contentType() != null ? view.contentType() : view.declaredMimeType(),
                    view.requirementId(), view.replacesDocumentId());
        }
    }

    @JsonInclude(JsonInclude.Include.NON_NULL)
    record DocumentList(List<Document> items, String nextCursor) {
    }

    record DocumentRequirements(long requirementsVersion, List<DocumentRequirementView> items) {
    }

    @JsonInclude(JsonInclude.Include.NON_NULL)
    record ExtractionField(String name, String value, double confidence, Integer page) {
    }

    record Extraction(
            String extractionId, String documentId, long documentVersion, List<ExtractionField> fields,
            String modelVersion, String objectVersion) {

        static Extraction of(ExtractionView view) {
            return new Extraction(view.extractionId(), view.documentId(), view.documentVersion(),
                    view.fields().stream()
                            .map(field -> new ExtractionField(field.name(), field.value(), field.confidence(),
                                    field.page()))
                            .toList(),
                    view.modelVersion(), view.objectVersion());
        }
    }

    private final DocumentService documents;

    DocumentController(DocumentService documents) {
        this.documents = documents;
    }

    @GetMapping("/api/v1/applications/{applicationId}/document-requirements")
    DocumentRequirements requirements(
            AuthenticatedSession session, @RequestHeader(CONTEXT) long context, @PathVariable String applicationId) {
        return new DocumentRequirements(documents.requirementsVersion(session, applicationId),
                documents.requirements(session, applicationId));
    }

    @PostMapping(path = "/api/v1/applications/{applicationId}/documents/upload-intents", consumes = "application/json")
    ResponseEntity<UploadIntent> uploadIntent(
            AuthenticatedSession session,
            @RequestHeader(CONTEXT) long context,
            @RequestHeader(IdempotencyKeys.HEADER) String idempotencyKey,
            @PathVariable String applicationId,
            @Valid @RequestBody UploadInput body) {
        DocumentCommands.UploadIntent intent =
                documents.createUploadIntent(session, applicationId, idempotencyKey, body.toCommand());
        return ResponseEntity.status(HttpStatus.CREATED).body(new UploadIntent(intent.uploadId(), intent.documentId(),
                intent.uploadUrl(), intent.grant(), intent.expiresAt(), intent.maxBytes()));
    }

    @DeleteMapping("/api/v1/uploads/{uploadId}")
    ResponseEntity<Void> cancel(
            AuthenticatedSession session, @RequestHeader(CONTEXT) long context, @PathVariable String uploadId) {
        documents.cancelUpload(session, uploadId);
        return ResponseEntity.noContent().build();
    }

    @GetMapping("/api/v1/applications/{applicationId}/documents")
    ResponseEntity<DocumentList> list(
            AuthenticatedSession session,
            @RequestHeader(CONTEXT) long context,
            @PathVariable String applicationId,
            @RequestParam(required = false) @Size(max = 2048) String cursor,
            @RequestParam(defaultValue = "20") @Min(1) @Max(100) int limit) {
        DocumentService.CursorPage page = documents.list(session, applicationId, cursor, limit);
        String etag = "\"l" + Digests.sha256(page.items().stream()
                .map(item -> item.documentId() + ":" + item.version()).toList().toString()).substring(0, 16) + "\"";
        return ResponseEntity.ok().eTag(etag)
                .body(new DocumentList(page.items().stream().map(Document::of).toList(), page.nextCursor()));
    }

    @GetMapping("/api/v1/documents/{documentId}")
    Document get(AuthenticatedSession session, @RequestHeader(CONTEXT) long context, @PathVariable String documentId) {
        return Document.of(documents.get(session, documentId));
    }

    @GetMapping("/api/v1/documents/{documentId}/extraction")
    Extraction extraction(
            AuthenticatedSession session, @RequestHeader(CONTEXT) long context, @PathVariable String documentId) {
        return Extraction.of(documents.extraction(session, documentId));
    }

    @PostMapping("/api/v1/documents/{documentId}/download-intents")
    ResponseEntity<DownloadIntent> downloadIntent(
            AuthenticatedSession session, @RequestHeader(CONTEXT) long context, @PathVariable String documentId) {
        DocumentCommands.DownloadIntent intent = documents.createDownloadIntent(session, documentId);
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(new DownloadIntent(intent.downloadUrl(), intent.grant(), intent.expiresAt()));
    }
}
