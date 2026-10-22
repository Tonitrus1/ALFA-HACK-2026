package ru.alfahack.credit.documents.application;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Base64;
import java.util.List;
import java.util.Optional;
import java.util.Set;

import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

import ru.alfahack.credit.access.application.AuthenticatedSession;
import ru.alfahack.credit.access.application.CompanyAccessService;
import ru.alfahack.credit.access.application.CompanyAction;
import ru.alfahack.credit.applications.application.ApplicationService;
import ru.alfahack.credit.applications.application.ApplicationView;
import ru.alfahack.credit.catalog.application.CatalogService;
import ru.alfahack.credit.catalog.application.DocumentRequirementView;
import ru.alfahack.credit.catalog.application.ProductView;
import ru.alfahack.credit.documents.infrastructure.DocumentRepository;
import ru.alfahack.credit.documents.infrastructure.ExtractionRepository;
import ru.alfahack.credit.documents.infrastructure.JobRepository;
import ru.alfahack.credit.documents.infrastructure.TransferRepository;
import ru.alfahack.credit.documents.infrastructure.TransferRepository.DownloadGrant;
import ru.alfahack.credit.documents.infrastructure.TransferRepository.Upload;
import ru.alfahack.credit.platform.support.Digests;
import ru.alfahack.credit.platform.support.IdempotencyKeys;
import ru.alfahack.credit.platform.support.Ids;
import ru.alfahack.credit.platform.support.Times;
import ru.alfahack.credit.platform.support.Tokens;
import ru.alfahack.credit.platform.web.ApplicationException;
import ru.alfahack.credit.platform.web.ErrorKind;
import ru.alfahack.credit.ports.PortErrorClass;
import ru.alfahack.credit.ports.PortException;
import ru.alfahack.credit.ports.objects.ActorScope;
import ru.alfahack.credit.ports.objects.ObjectRef;
import ru.alfahack.credit.ports.objects.ObjectStorePort;
import ru.alfahack.credit.ports.objects.ScanStatus;

/**
 * Документы заявки и файловый шлюз (backend guide, раздел 4). Upload intent закрепляет компанию, заявку,
 * требование, тип и размер; грант короткоживущий, связан с сессией и действием. Байты идут потоково
 * в карантин; финализация и отмена конкурируют за один CAS upload-state. Скачивание — только точная CLEAN-версия.
 */
@Service
public class DocumentService {

    public static final long MAX_BYTES = 10L * 1024 * 1024;
    static final Duration UPLOAD_GRANT_TTL = Duration.ofMinutes(10);
    static final Duration DOWNLOAD_GRANT_TTL = Duration.ofMinutes(5);
    static final Set<String> CONTENT_TYPES = Set.of("application/pdf", "image/jpeg", "image/png");

    private final DocumentRepository documents;
    private final TransferRepository transfers;
    private final JobRepository jobs;
    private final ExtractionRepository extractions;
    private final ApplicationService applications;
    private final CatalogService catalog;
    private final CompanyAccessService companies;
    private final ObjectStorePort objects;
    private final TransactionTemplate transactions;
    private final Clock clock;

    public DocumentService(
            DocumentRepository documents,
            TransferRepository transfers,
            JobRepository jobs,
            ExtractionRepository extractions,
            ApplicationService applications,
            CatalogService catalog,
            CompanyAccessService companies,
            ObjectStorePort objects,
            TransactionTemplate transactions,
            Clock clock) {
        this.documents = documents;
        this.transfers = transfers;
        this.jobs = jobs;
        this.extractions = extractions;
        this.applications = applications;
        this.catalog = catalog;
        this.companies = companies;
        this.objects = objects;
        this.transactions = transactions;
        this.clock = clock;
    }

    public List<DocumentRequirementView> requirements(AuthenticatedSession session, String applicationId) {
        ApplicationView application = applications.get(session, applicationId);
        return catalog.requirements(application.productId(), application.productVersion());
    }

    public long requirementsVersion(AuthenticatedSession session, String applicationId) {
        ApplicationView application = applications.get(session, applicationId);
        return product(application).requirementsVersion();
    }

    public DocumentCommands.UploadIntent createUploadIntent(
            AuthenticatedSession session, String applicationId, String idempotencyKey,
            DocumentCommands.UploadRequest request) {
        IdempotencyKeys.validate(idempotencyKey);
        ApplicationView application = applications.get(session, applicationId);
        companies.requireAction(session, application.companyId(), CompanyAction.UPLOAD_DOCUMENT);
        String digest = Digests.sha256(applicationId + "|" + request);

        return transactions.execute(status -> {
            Instant now = Times.now(clock);
            Optional<Upload> existing =
                    transfers.findUploadByKey(session.actorId(), application.companyId(), idempotencyKey);
            if (existing.isPresent()) {
                return replayIntent(existing.get(), digest, now);
            }
            if (request.requestId() != null || request.requestVersion() != null) {
                throw DocumentErrors.unprocessable(
                        "INFORMATION_REQUEST_NOT_FOUND", "Запрос дополнительной информации не найден");
            }
            if (!"DRAFT".equals(application.status())) {
                throw DocumentErrors.conflict("APPLICATION_NOT_EDITABLE", "Заявка уже отправлена");
            }
            ProductView product = product(application);
            if (product.requirementsVersion() != request.requirementsVersion()) {
                throw DocumentErrors.conflict("DOCUMENT_REQUIREMENTS_CHANGED", "Требования к документам изменились");
            }
            DocumentRequirementView requirement = catalog.requirements(product.productId(), product.version())
                    .stream()
                    .filter(found -> found.requirementId().equals(request.requirementId()))
                    .findFirst()
                    .orElseThrow(() -> DocumentErrors.unprocessable("REQUIREMENT_NOT_FOUND", "Нет такого требования"));
            if (!CONTENT_TYPES.contains(request.declaredMimeType())
                    || !requirement.allowedContentTypes().contains(request.declaredMimeType())) {
                throw DocumentErrors.unprocessable("UNSUPPORTED_CONTENT_TYPE", "Тип файла не поддерживается");
            }
            long maxBytes = Math.min(MAX_BYTES, requirement.maxBytes());
            if (request.sizeBytes() < 1 || request.sizeBytes() > maxBytes) {
                throw DocumentErrors.unprocessable("FILE_TOO_LARGE", "Файл больше допустимого размера");
            }
            requireReplaceable(application, request);

            String documentId = Ids.newId();
            documents.insert(new DocumentView(
                    documentId, applicationId, application.companyId(), requirement.requirementId(),
                    request.requirementsVersion(), request.documentType(), request.fileName(),
                    request.declaredMimeType(), request.sizeBytes(), null, null, null, null, null, "UPLOADING",
                    "NOT_REQUESTED", null, Math.min(requirement.maxPagesForExtraction(), FileInspector.MAX_PAGES),
                    request.replacesDocumentId(), 1, session.actorId(), now, now));
            String uploadId = Ids.newId();
            String transferId = Ids.newId();
            String grant = Tokens.random();
            Instant expiresAt = now.plus(UPLOAD_GRANT_TTL);
            if (!transfers.insertUpload(new Upload(
                    uploadId, transferId, documentId, Digests.sha256(grant), session.sessionHash(), session.actorId(),
                    application.companyId(), request.sizeBytes(), "PENDING", 1, idempotencyKey, digest, expiresAt,
                    now))) {
                throw IdempotencyKeys.reused();
            }
            return new DocumentCommands.UploadIntent(
                    uploadId, documentId, uploadUrl(transferId), grant, expiresAt, request.sizeBytes());
        });
    }

    /**
     * Потоковая загрузка в карантин. Грант, сессия, компания, срок и тип проверяются до чтения тела;
     * размер — при записи и после. Финализация: CAS PENDING→COMPLETED, документ QUARANTINED, задание SCAN.
     */
    public void receiveUpload(
            AuthenticatedSession session, String transferId, String grant, String contentType, InputStream body) {
        Upload upload = transfers.findUploadByTransfer(transferId)
                .filter(found -> found.companyId().equals(session.selectedCompanyId())
                        && session.isMemberOf(found.companyId()))
                .orElseThrow(ApplicationException::notFound);
        if (!upload.sessionHash().equals(session.sessionHash()) || !Tokens.matchesHash(grant, upload.grantHash())) {
            throw DocumentErrors.forbidden("UPLOAD_GRANT_INVALID", "Разрешение загрузки недействительно");
        }
        if (!"PENDING".equals(upload.state())) {
            throw DocumentErrors.conflict("UPLOAD_NOT_PENDING", "Загрузка уже завершена или отменена");
        }
        if (!clock.instant().isBefore(upload.expiresAt())) {
            throw DocumentErrors.conflict("UPLOAD_EXPIRED", "Срок разрешения загрузки истёк");
        }
        DocumentView document = documents.find(upload.documentId()).orElseThrow(ApplicationException::notFound);
        if (contentType == null || !document.declaredMimeType().equals(stripParameters(contentType))) {
            throw DocumentErrors.unprocessable("FILE_TYPE_MISMATCH", "Тип файла не совпадает с объявленным");
        }

        ObjectRef stored;
        try {
            stored = objects.putQuarantine(body, upload.maxBytes());
        } catch (PortException e) {
            throw e.errorClass() == PortErrorClass.INVALID_INPUT
                    ? DocumentErrors.unprocessable("FILE_TOO_LARGE", "Файл больше объявленного размера")
                    : DocumentErrors.fromPort(e);
        }
        if (stored.size() != document.declaredSizeBytes()) {
            throw DocumentErrors.unprocessable("FILE_SIZE_MISMATCH", "Размер файла не совпадает с объявленным");
        }

        transactions.executeWithoutResult(status -> {
            Instant now = Times.now(clock);
            if (!transfers.transitionUpload(upload.uploadId(), upload.version(), "COMPLETED")) {
                throw DocumentErrors.conflict("UPLOAD_NOT_PENDING", "Загрузка уже завершена или отменена");
            }
            String objectVersion = DocumentView.objectVersion(stored.objectId(), stored.version());
            if (!documents.markQuarantined(document.documentId(), stored.objectId(), objectVersion,
                    document.declaredMimeType(), stored.size(), stored.sha256(), now)) {
                throw DocumentErrors.conflict("UPLOAD_NOT_PENDING", "Документ уже не ожидает загрузки");
            }
            jobs.insert(Ids.newId(), document.documentId(), "SCAN", objectVersion, now);
        });
    }

    /** Отмена незавершённой загрузки тем же CAS; проигравшие байты не становятся доступными. */
    public void cancelUpload(AuthenticatedSession session, String uploadId) {
        Upload upload = transfers.findUpload(uploadId)
                .filter(found -> found.companyId().equals(session.selectedCompanyId())
                        && session.isMemberOf(found.companyId()))
                .orElseThrow(ApplicationException::notFound);
        transactions.executeWithoutResult(status -> {
            if (!transfers.transitionUpload(upload.uploadId(), upload.version(), "CANCELLED")) {
                throw DocumentErrors.conflict("UPLOAD_NOT_PENDING", "Загрузка уже завершена или отменена");
            }
            documents.transitionScan(upload.documentId(), "UPLOADING", "DELETED", null, null, Times.now(clock));
        });
    }

    public CursorPage list(AuthenticatedSession session, String applicationId, String cursor, int limit) {
        applications.get(session, applicationId);
        Cursor after = Cursor.parse(cursor);
        List<DocumentView> rows = documents.listForApplication(applicationId, after.at(), after.id(), limit + 1);
        if (rows.size() <= limit) {
            return new CursorPage(rows, null);
        }
        List<DocumentView> page = List.copyOf(rows.subList(0, limit));
        return new CursorPage(page, Cursor.of(page.getLast()));
    }

    public DocumentView get(AuthenticatedSession session, String documentId) {
        return documents.find(documentId)
                .filter(found -> found.companyId().equals(session.selectedCompanyId())
                        && session.isMemberOf(found.companyId()))
                .orElseThrow(ApplicationException::notFound);
    }

    public ExtractionView extraction(AuthenticatedSession session, String documentId) {
        DocumentView document = get(session, documentId);
        return Optional.ofNullable(document.extractionId())
                .flatMap(extractions::find)
                .filter(found -> "READY".equals(found.status()) && found.objectVersion().equals(document.objectVersion()))
                .orElseThrow(() -> new ApplicationException(
                        ErrorKind.NOT_FOUND, "EXTRACTION_NOT_READY",
                        "Распознанные значения ещё не готовы"));
    }

    public DocumentCommands.DownloadIntent createDownloadIntent(AuthenticatedSession session, String documentId) {
        DocumentView document = get(session, documentId);
        companies.requireAction(session, document.companyId(), CompanyAction.DOWNLOAD_DOCUMENT);
        if (!"CLEAN".equals(document.scanState())) {
            throw DocumentErrors.conflict("DOCUMENT_NOT_CLEAN", "Документ ещё не проверен");
        }
        Instant now = Times.now(clock);
        String transferId = Ids.newId();
        String grant = Tokens.random();
        Instant expiresAt = now.plus(DOWNLOAD_GRANT_TTL);
        transfers.insertDownloadGrant(new DownloadGrant(
                transferId, Digests.sha256(grant), session.sessionHash(), documentId, document.objectVersion(),
                expiresAt), now);
        return new DocumentCommands.DownloadIntent("/api/v1/files/downloads/" + transferId, grant, expiresAt);
    }

    /** Права и точная CLEAN-версия перепроверяются при открытии. */
    public InputStream openDownload(AuthenticatedSession session, String transferId, String grant) {
        DownloadGrant download = transfers.findDownloadGrant(transferId).orElseThrow(ApplicationException::notFound);
        DocumentView document = get(session, download.documentId());
        if (!download.sessionHash().equals(session.sessionHash()) || !Tokens.matchesHash(grant, download.grantHash())) {
            throw DocumentErrors.forbidden("DOWNLOAD_GRANT_INVALID", "Разрешение скачивания недействительно");
        }
        if (!clock.instant().isBefore(download.expiresAt())) {
            throw DocumentErrors.conflict("DOWNLOAD_EXPIRED", "Срок разрешения скачивания истёк");
        }
        companies.requireAction(session, document.companyId(), CompanyAction.DOWNLOAD_DOCUMENT);
        if (!"CLEAN".equals(document.scanState()) || !document.objectVersion().equals(download.objectVersion())) {
            throw DocumentErrors.conflict("DOCUMENT_NOT_CLEAN", "Версия документа недоступна");
        }
        try {
            return objects.openClean(document.objectRef(ScanStatus.CLEAN),
                    new ActorScope(session.actorId(), document.companyId()));
        } catch (PortException e) {
            throw DocumentErrors.fromPort(e);
        }
    }

    private DocumentCommands.UploadIntent replayIntent(Upload existing, String digest, Instant now) {
        if (!existing.bodyDigest().equals(digest)) {
            throw IdempotencyKeys.reused();
        }
        if (!"PENDING".equals(existing.state())) {
            throw DocumentErrors.conflict("UPLOAD_NOT_PENDING", "Загрузка уже завершена или отменена");
        }
        String grant = Tokens.random();
        Instant expiresAt = now.plus(UPLOAD_GRANT_TTL);
        transfers.rotateGrant(existing.uploadId(), Digests.sha256(grant), expiresAt);
        return new DocumentCommands.UploadIntent(existing.uploadId(), existing.documentId(),
                uploadUrl(existing.transferId()), grant, expiresAt, existing.maxBytes());
    }

    private void requireReplaceable(ApplicationView application, DocumentCommands.UploadRequest request) {
        if ((request.replacesDocumentId() == null) != (request.expectedDocumentVersion() == null)) {
            throw DocumentErrors.unprocessable("INVALID_REQUEST", "replacesDocumentId и expectedDocumentVersion парные");
        }
        if (request.replacesDocumentId() == null) {
            return;
        }
        DocumentView replaced = documents.find(request.replacesDocumentId())
                .filter(found -> found.applicationId().equals(application.applicationId()))
                .orElseThrow(ApplicationException::notFound);
        if (replaced.version() != request.expectedDocumentVersion()) {
            throw DocumentErrors.conflict("DOCUMENT_VERSION_CONFLICT", "Документ изменился");
        }
    }

    private ProductView product(ApplicationView application) {
        return catalog.find(application.productId(), application.productVersion()).orElseThrow();
    }

    private static String uploadUrl(String transferId) {
        return "/api/v1/files/uploads/" + transferId;
    }

    private static String stripParameters(String contentType) {
        int separator = contentType.indexOf(';');
        return (separator < 0 ? contentType : contentType.substring(0, separator)).trim().toLowerCase();
    }

    public record CursorPage(List<DocumentView> items, String nextCursor) {
    }

    record Cursor(Instant at, String id) {

        static Cursor parse(String cursor) {
            if (cursor == null) {
                return new Cursor(null, null);
            }
            try {
                String raw = new String(Base64.getUrlDecoder().decode(cursor), StandardCharsets.UTF_8);
                int separator = raw.indexOf(':');
                long micros = Long.parseLong(raw.substring(0, separator));
                return new Cursor(Instant.ofEpochSecond(micros / 1_000_000, (micros % 1_000_000) * 1_000),
                        raw.substring(separator + 1));
            } catch (RuntimeException e) {
                throw new ApplicationException(
                        ErrorKind.INVALID_REQUEST, "INVALID_CURSOR", "Некорректный курсор");
            }
        }

        static String of(DocumentView last) {
            Instant at = last.createdAt();
            long micros = at.getEpochSecond() * 1_000_000 + at.getNano() / 1_000;
            return Base64.getUrlEncoder().withoutPadding()
                    .encodeToString((micros + ":" + last.documentId()).getBytes(StandardCharsets.UTF_8));
        }
    }
}
