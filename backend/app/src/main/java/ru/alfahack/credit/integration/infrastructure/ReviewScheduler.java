package ru.alfahack.credit.integration.infrastructure;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import ru.alfahack.credit.integration.application.ReviewWorker;

/** Опрос очереди рассмотрения дел симулятором. */
@Component
@ConditionalOnProperty(name = "credit.scheduling.enabled", havingValue = "true", matchIfMissing = true)
class ReviewScheduler {

    private final ReviewWorker worker;

    ReviewScheduler(ReviewWorker worker) {
        this.worker = worker;
    }

    @Scheduled(fixedDelayString = "${credit.review.poll-interval:PT2S}")
    void poll() {
        while (worker.processOnce()) {
            // рассматриваем, пока есть задачи
        }
    }
}
