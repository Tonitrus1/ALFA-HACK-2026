package ru.alfahack.credit.documents.application;

import java.util.List;

import org.springframework.stereotype.Component;

import ru.alfahack.credit.applications.application.ApplicationCommands;
import ru.alfahack.credit.applications.application.ApplicationView;
import ru.alfahack.credit.applications.application.DocumentReferenceGate;
import ru.alfahack.credit.documents.infrastructure.DocumentRepository;

/**
 * Точные ссылки пакета: документ той же заявки и компании, CLEAN, наблюдённая documentVersion и objectVersion
 * совпадают с текущими. Неизвестная или устаревшая ссылка недопустима.
 */
@Component
class CleanDocumentGate implements DocumentReferenceGate {

    private final DocumentRepository documents;

    CleanDocumentGate(DocumentRepository documents) {
        this.documents = documents;
    }

    @Override
    public boolean allClean(ApplicationView application, List<ApplicationCommands.DocumentReference> references) {
        return references.stream().allMatch(reference -> documents.find(reference.documentId())
                .filter(document -> document.applicationId().equals(application.applicationId())
                        && document.companyId().equals(application.companyId())
                        && "CLEAN".equals(document.scanState())
                        && document.version() == reference.documentVersion()
                        && reference.objectVersion().equals(document.objectVersion()))
                .isPresent());
    }
}
