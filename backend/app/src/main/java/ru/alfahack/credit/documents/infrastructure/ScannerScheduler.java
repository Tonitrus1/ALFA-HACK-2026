package ru.alfahack.credit.documents.infrastructure;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import ru.alfahack.credit.documents.application.ScannerWorker;

/** Опрос SCAN-заданий in-process сканером; выключается credit.scanner.enabled=false (внешний сканер). */
@Component
@ConditionalOnProperty(name = {"credit.scheduling.enabled", "credit.scanner.enabled"}, havingValue = "true",
        matchIfMissing = true)
class ScannerScheduler {

    private final ScannerWorker worker;

    ScannerScheduler(ScannerWorker worker) {
        this.worker = worker;
    }

    @Scheduled(fixedDelayString = "${credit.scanner.poll-interval:PT2S}")
    void poll() {
        while (worker.processOnce()) {
            // обрабатываем очередь до пустой
        }
    }
}
