package ru.alfahack.credit.documents.application;

import java.io.InputStream;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Optional;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import ru.alfahack.credit.documents.infrastructure.DocumentRepository;
import ru.alfahack.credit.documents.infrastructure.ExtractionRepository;
import ru.alfahack.credit.documents.infrastructure.JobRepository;
import ru.alfahack.credit.documents.infrastructure.JobRepository.Lease;
import ru.alfahack.credit.platform.support.Digests;
import ru.alfahack.credit.platform.support.Ids;
import ru.alfahack.credit.platform.support.Times;
import ru.alfahack.credit.platform.support.Tokens;
import ru.alfahack.credit.ports.PortException;
import ru.alfahack.credit.ports.objects.ActorScope;
import ru.alfahack.credit.ports.objects.ObjectRef;
import ru.alfahack.credit.ports.objects.ObjectStorePort;
import ru.alfahack.credit.ports.objects.ScanReceipt;
import ru.alfahack.credit.ports.objects.ScanStatus;

/**
 * Задания SCAN/EXTRACT с арендой (workerId, leaseToken, generation, срок, objectVersion). Результат принимается
 * только от текущего поколения непросроченной аренды для той же версии объекта; иначе 409 LEASE_STALE.
 * CLEAN требует положительного вердикта, совпадения версии и хеша; ERROR оставляет файл в карантине.
 */
@Service
public class DocumentJobService {

    public static final String SCAN = "SCAN";
    public static final String EXTRACT = "EXTRACT";
    static final Duration LEASE = Duration.ofMinutes(2);
    static final int MAX_SCAN_ATTEMPTS = 5;

    private final JobRepository jobs;
    private final DocumentRepository documents;
    private final ExtractionRepository extractions;
    private final ObjectStorePort objects;
    private final Clock clock;

    public DocumentJobService(
            JobRepository jobs, DocumentRepository documents, ExtractionRepository extractions,
            ObjectStorePort objects, Clock clock) {
        this.jobs = jobs;
        this.documents = documents;
        this.extractions = extractions;
        this.objects = objects;
        this.clock = clock;
    }

    @Transactional
    public Optional<JobCommands.JobLease> claim(String workerId, String jobType) {
        Instant now = Times.now(clock);
        String token = Tokens.random();
        return jobs.claim(jobType, workerId, Digests.sha256(token), now, now.plus(LEASE))
                .map(lease -> new JobCommands.JobLease(
                        lease.jobId(), lease.generation(), lease.leaseUntil(), lease.documentId(),
                        lease.objectVersion(), objectId(lease.objectVersion()), lease.jobType(), token));
    }

    @Transactional
    public JobCommands.JobLease renew(String jobId, String jobType, JobCommands.LeaseProof proof) {
        Instant now = Times.now(clock);
        Lease lease = currentLease(jobId, jobType, proof, now);
        Instant until = now.plus(LEASE);
        jobs.renew(jobId, until, now);
        return new JobCommands.JobLease(lease.jobId(), lease.generation(), until, lease.documentId(),
                lease.objectVersion(), objectId(lease.objectVersion()), lease.jobType(), proof.leaseToken());
    }

    @Transactional
    public JobCommands.Receipt recordScan(String jobId, JobCommands.ScanResult result) {
        Instant now = Times.now(clock);
        Lease lease = currentLease(jobId, SCAN, result.lease(), now);
        requireSameObject(lease, result.objectVersion());
        DocumentView document = documents.lock(lease.documentId()).orElseThrow();
        if (!"QUARANTINED".equals(document.scanState()) || !lease.objectVersion().equals(document.objectVersion())) {
            jobs.finish(jobId, "DONE", "STALE_DOCUMENT", now);
            throw DocumentErrors.conflict("LEASE_STALE", "Документ изменился");
        }
        switch (result.verdict()) {
            case "CLEAN" -> {
                if (!document.objectId().equals(result.cleanObjectRef())) {
                    throw DocumentErrors.unprocessable("CLEAN_OBJECT_MISMATCH", "Ссылка на чистый объект не совпадает");
                }
                ObjectRef quarantined = document.objectRef(ScanStatus.QUARANTINED);
                try {
                    objects.promote(quarantined, new ScanReceipt(
                            quarantined.objectId(), quarantined.version(), quarantined.sha256(), ScanStatus.CLEAN));
                } catch (PortException e) {
                    throw DocumentErrors.fromPort(e);
                }
                documents.transitionScan(document.documentId(), "QUARANTINED", "CLEAN", document.objectVersion(),
                        "PENDING", now);
                if (document.replacesDocumentId() != null) {
                    documents.find(document.replacesDocumentId())
                            .filter(old -> "CLEAN".equals(old.scanState()))
                            .ifPresent(old -> documents.transitionScan(
                                    old.documentId(), "CLEAN", "DELETED", old.objectVersion(), null, now));
                }
                jobs.finish(jobId, "DONE", null, now);
                jobs.insert(Ids.newId(), document.documentId(), EXTRACT, document.objectVersion(), now);
            }
            case "REJECTED" -> {
                documents.transitionScan(document.documentId(), "QUARANTINED", "REJECTED", document.objectVersion(),
                        null, now);
                jobs.finish(jobId, "DONE", "REJECTED", now);
            }
            case "ERROR" -> {
                int attempts = lease.attempts() + 1;
                boolean failed = attempts >= MAX_SCAN_ATTEMPTS;
                jobs.retryOrFail(jobId, attempts, failed, now.plus(backoff(attempts)), "SCANNER_ERROR", now);
            }
            default -> throw DocumentErrors.unprocessable("INVALID_VERDICT", "Неизвестный вердикт");
        }
        return new JobCommands.Receipt(Ids.newId(), now);
    }

    @Transactional
    public JobCommands.Receipt recordExtraction(String jobId, JobCommands.ExtractionResult result) {
        Instant now = Times.now(clock);
        Lease lease = currentLease(jobId, EXTRACT, result.lease(), now);
        requireSameObject(lease, result.objectVersion());
        DocumentView document = documents.lock(lease.documentId()).orElseThrow();
        if (!"CLEAN".equals(document.scanState()) || !lease.objectVersion().equals(document.objectVersion())) {
            jobs.finish(jobId, "DONE", "STALE_DOCUMENT", now);
            throw DocumentErrors.conflict("LEASE_STALE", "Документ изменился");
        }
        String extractionId = Ids.newId();
        extractions.insert(new ExtractionView(extractionId, document.documentId(), document.version(),
                document.objectVersion(), result.engineVersion(), result.status(), result.fields()), now);
        documents.recordExtraction(document.documentId(), document.objectVersion(), result.status(), extractionId, now);
        jobs.finish(jobId, "DONE", "FAILED".equals(result.status()) ? "EXTRACTION_FAILED" : null, now);
        return new JobCommands.Receipt(extractionId, now);
    }

    @Transactional
    public InputStream openExtractionInput(String jobId, JobCommands.LeaseProof proof) {
        Lease lease=currentLease(jobId, EXTRACT, proof, Times.now(clock));
        DocumentView document=documents.find(lease.documentId()).orElseThrow();
        if (!"CLEAN".equals(document.scanState()) || !lease.objectVersion().equals(document.objectVersion())) {
            throw DocumentErrors.conflict("LEASE_STALE", "Документ изменился");
        }
        return objects.openClean(document.objectRef(ScanStatus.CLEAN),
                new ActorScope("document-ocr", document.companyId()));
    }

    private Lease currentLease(String jobId, String jobType, JobCommands.LeaseProof proof, Instant now) {
        return jobs.lockCurrentLease(jobId, jobType, proof.generation(), proof.workerId(),
                        Digests.sha256(proof.leaseToken()), now)
                .orElseThrow(() -> DocumentErrors.conflict("LEASE_STALE", "Аренда задания недействительна"));
    }

    private static void requireSameObject(Lease lease, String objectVersion) {
        if (!lease.objectVersion().equals(objectVersion)) {
            throw DocumentErrors.conflict("LEASE_STALE", "Версия объекта не совпадает с арендой");
        }
    }

    static Duration backoff(int attempts) {
        return Duration.ofSeconds(Math.min(300, 5L << Math.min(attempts, 6)));
    }

    private static String objectId(String objectVersion) {
        return objectVersion.substring(0, objectVersion.lastIndexOf(":v"));
    }
}
