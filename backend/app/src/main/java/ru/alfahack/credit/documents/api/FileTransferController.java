package ru.alfahack.credit.documents.api;

import java.io.IOException;
import java.io.InputStream;

import jakarta.servlet.http.HttpServletRequest;

import org.springframework.core.io.InputStreamResource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RestController;

import ru.alfahack.credit.access.application.AuthenticatedSession;
import ru.alfahack.credit.documents.application.DocumentService;

/**
 * Файловый шлюз того же origin. Сессия, CSRF (для PUT) и X-Company-Context проверяет перехватчик сессии;
 * грант передаётся только заголовком и не логируется. Тело читается потоком, без буфера всего файла.
 */
@RestController
class FileTransferController {

    private final DocumentService documents;

    FileTransferController(DocumentService documents) {
        this.documents = documents;
    }

    @PutMapping(path = "/api/v1/files/uploads/{transferId}", consumes = {"application/pdf", "image/jpeg", "image/png"})
    ResponseEntity<Void> upload(
            AuthenticatedSession session,
            @RequestHeader("X-Company-Context") long context,
            @RequestHeader("X-Upload-Grant") String grant,
            @PathVariable String transferId,
            HttpServletRequest request) throws IOException {
        try (InputStream body = request.getInputStream()) {
            documents.receiveUpload(session, transferId, grant, request.getContentType(), body);
        }
        return ResponseEntity.noContent().build();
    }

    @GetMapping("/api/v1/files/downloads/{transferId}")
    ResponseEntity<InputStreamResource> download(
            AuthenticatedSession session,
            @RequestHeader("X-Company-Context") long context,
            @RequestHeader("X-Download-Grant") String grant,
            @PathVariable String transferId) {
        InputStream content = documents.openDownload(session, transferId, grant);
        return ResponseEntity.ok()
                .contentType(MediaType.APPLICATION_OCTET_STREAM)
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"document\"")
                .header("X-Content-Type-Options", "nosniff")
                .body(new InputStreamResource(content));
    }
}
