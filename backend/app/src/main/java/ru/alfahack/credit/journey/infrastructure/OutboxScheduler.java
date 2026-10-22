package ru.alfahack.credit.journey.infrastructure;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import ru.alfahack.credit.journey.application.OutboxDispatcher;

/** Периодическая доставка outbox; в тестах выключена (credit.scheduling.enabled=false). */
@Component
@ConditionalOnProperty(name = "credit.scheduling.enabled", havingValue = "true", matchIfMissing = true)
class OutboxScheduler {

    private final OutboxDispatcher dispatcher;

    OutboxScheduler(OutboxDispatcher dispatcher) {
        this.dispatcher = dispatcher;
    }

    @Scheduled(fixedDelayString = "${credit.outbox.poll-interval:PT1S}")
    void dispatch() {
        dispatcher.dispatchOnce();
    }
}
