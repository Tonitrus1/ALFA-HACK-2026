package ru.alfahack.credit.documents.application;

import java.time.Instant;

public final class DocumentCommands {

    private DocumentCommands() {
    }

    public record UploadRequest(
            String fileName,
            String declaredMimeType,
            long sizeBytes,
            String documentType,
            String requestId,
            Long requestVersion,
            String requirementId,
            long requirementsVersion,
            String replacesDocumentId,
            Long expectedDocumentVersion) {
    }

    public record UploadIntent(
            String uploadId, String documentId, String uploadUrl, String grant, Instant expiresAt, long maxBytes) {

        @Override
        public String toString() {
            return "UploadIntent[uploadId=" + uploadId + ", documentId=" + documentId + "]";
        }
    }

    public record DownloadIntent(String downloadUrl, String grant, Instant expiresAt) {

        @Override
        public String toString() {
            return "DownloadIntent[url=" + downloadUrl + "]";
        }
    }
}
