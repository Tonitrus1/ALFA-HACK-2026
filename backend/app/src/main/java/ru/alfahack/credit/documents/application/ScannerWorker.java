package ru.alfahack.credit.documents.application;

import java.io.IOException;
import java.io.InputStream;
import java.util.Optional;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import ru.alfahack.credit.documents.infrastructure.DocumentRepository;
import ru.alfahack.credit.platform.support.Ids;
import ru.alfahack.credit.platform.web.ApplicationException;
import ru.alfahack.credit.ports.PortException;
import ru.alfahack.credit.ports.objects.ObjectStorePort;
import ru.alfahack.credit.ports.objects.ScanStatus;

/**
 * Служебная роль file-scanner внутри процесса backend: берёт SCAN-задание с арендой, проверяет сигнатуру и
 * структуру, затем ClamAV, и сдаёт результат тем же путём, что и внешний сканер. Сканер не меняет состояние
 * документа сам — переход из карантина выполняет {@link DocumentJobService}.
 */
@Component
public class ScannerWorker {

    private static final Logger log = LoggerFactory.getLogger(ScannerWorker.class);
    static final String STRUCTURE_ENGINE = "structure-check/1";

    private final DocumentJobService jobs;
    private final DocumentRepository documents;
    private final ObjectStorePort objects;
    private final FileInspector inspector;
    private final MalwareScanner scanner;
    private final String workerId;

    public ScannerWorker(
            DocumentJobService jobs, DocumentRepository documents, ObjectStorePort objects, FileInspector inspector,
            MalwareScanner scanner, @Value("${credit.scanner.worker-id:}") String workerId) {
        this.jobs = jobs;
        this.documents = documents;
        this.objects = objects;
        this.inspector = inspector;
        this.scanner = scanner;
        this.workerId = workerId.isBlank() ? "scanner-" + Ids.newId() : workerId;
    }

    /** Обрабатывает одно задание; false — заданий нет. */
    public boolean processOnce() {
        Optional<JobCommands.JobLease> claimed = jobs.claim(workerId, DocumentJobService.SCAN);
        if (claimed.isEmpty()) {
            return false;
        }
        JobCommands.JobLease lease = claimed.get();
        JobCommands.LeaseProof proof = new JobCommands.LeaseProof(workerId, lease.generation(), lease.leaseToken());
        String verdict;
        String engine;
        try {
            DocumentView document = documents.find(lease.documentId()).orElseThrow();
            byte[] bytes;
            try (InputStream in = objects.openQuarantine(document.objectRef(ScanStatus.QUARANTINED))) {
                bytes = in.readAllBytes();
            }
            FileInspector.Result inspection = inspector.inspect(bytes, document.declaredMimeType(), document.maxPages());
            if (inspection instanceof FileInspector.Result.Rejected rejected) {
                verdict = "REJECTED";
                engine = STRUCTURE_ENGINE;
                log.info("Document rejected by structure check jobId={} reason={}", lease.jobId(), rejected.reason());
            } else {
                MalwareScanner.Verdict scanned = scanner.scan(bytes);
                engine = scanned.engineVersion();
                verdict = switch (scanned.outcome()) {
                    case CLEAN -> "CLEAN";
                    case INFECTED -> "REJECTED";
                    case ERROR -> "ERROR";
                };
                if (scanned.outcome() != MalwareScanner.Outcome.CLEAN) {
                    log.warn("Document scan outcome={} jobId={} detail={}", scanned.outcome(), lease.jobId(),
                            scanned.detail());
                }
            }
        } catch (IOException | PortException e) {
            verdict = "ERROR";
            engine = STRUCTURE_ENGINE;
            log.warn("Document scan read failed jobId={} error={}", lease.jobId(), e.getClass().getSimpleName());
        }
        try {
            jobs.recordScan(lease.jobId(), new JobCommands.ScanResult(proof, lease.objectVersion(), verdict, engine,
                    "CLEAN".equals(verdict) ? lease.objectRef() : null));
        } catch (ApplicationException e) {
            log.warn("Scan result not recorded jobId={} code={}", lease.jobId(), e.code());
        }
        return true;
    }
}
