package ru.alfahack.credit.documents.application;

import java.time.Instant;

import ru.alfahack.credit.ports.objects.ObjectRef;
import ru.alfahack.credit.ports.objects.ScanStatus;

/** Документ заявки. objectVersion — неизменная версия байтов вида "{objectId}:v{n}". */
public record DocumentView(
        String documentId,
        String applicationId,
        String companyId,
        String requirementId,
        long requirementsVersion,
        String documentType,
        String fileName,
        String declaredMimeType,
        long declaredSizeBytes,
        String contentType,
        Long sizeBytes,
        String sha256,
        String objectId,
        String objectVersion,
        String scanState,
        String extractionState,
        String extractionId,
        int maxPages,
        String replacesDocumentId,
        long version,
        String createdBy,
        Instant createdAt,
        Instant updatedAt) {

    public static String objectVersion(String objectId, long version) {
        return objectId + ":v" + version;
    }

    /** Точная ссылка на байты для ObjectStorePort; только после финализации загрузки. */
    public ObjectRef objectRef(ScanStatus status) {
        long objectVersionNumber = Long.parseLong(objectVersion.substring(objectVersion.lastIndexOf(":v") + 2));
        return new ObjectRef(objectId, objectVersionNumber, sha256, sizeBytes, contentType, status);
    }
}
