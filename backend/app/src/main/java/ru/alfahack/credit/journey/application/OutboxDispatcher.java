package ru.alfahack.credit.journey.application;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.List;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

import ru.alfahack.credit.journey.infrastructure.OutboxRepository;
import ru.alfahack.credit.journey.infrastructure.OutboxRepository.ClaimedEvent;
import ru.alfahack.credit.platform.support.Ids;

/**
 * Локальный транспорт outbox → in-process обработчики (local-mvp). Захват партии через SKIP LOCKED с lease;
 * каждое событие доставляется в своей транзакции и подтверждается только владельцем актуальной lease.
 * Ошибка — повтор с backoff; после maxAttempts событие становится видимым FAILED, а не исчезает.
 */
@Service
public class OutboxDispatcher {

    private static final Logger log = LoggerFactory.getLogger(OutboxDispatcher.class);

    static final int BATCH_SIZE = 20;
    static final int MAX_ATTEMPTS = 10;
    static final Duration LEASE = Duration.ofSeconds(30);

    private final OutboxRepository outbox;
    private final List<EventHandler> handlers;
    private final TransactionTemplate transactions;
    private final Clock clock;
    private final String workerId = "dispatcher-" + Ids.newId();

    public OutboxDispatcher(
            OutboxRepository outbox, List<EventHandler> handlers, TransactionTemplate transactions, Clock clock) {
        this.outbox = outbox;
        this.handlers = List.copyOf(handlers);
        this.transactions = transactions;
        this.clock = clock;
    }

    /** Одна итерация доставки; возвращает число подтверждённых событий. */
    public int dispatchOnce() {
        Instant now = clock.instant();
        List<ClaimedEvent> claimed = transactions.execute(status ->
                outbox.claim(workerId, now, now.plus(LEASE), BATCH_SIZE));
        int delivered = 0;
        for (ClaimedEvent event : claimed) {
            if (deliver(event)) {
                delivered++;
            }
        }
        return delivered;
    }

    private boolean deliver(ClaimedEvent claimed) {
        try {
            transactions.executeWithoutResult(status -> {
                for (EventHandler handler : handlers) {
                    if (handler.handles(claimed.event().eventType())) {
                        handler.handle(claimed.event());
                    }
                }
                if (!outbox.markDelivered(claimed.event().eventId(), workerId, clock.instant())) {
                    throw new LeaseLostException();
                }
            });
            return true;
        } catch (LeaseLostException e) {
            log.warn("Outbox lease lost eventId={}", claimed.event().eventId());
            return false;
        } catch (RuntimeException e) {
            int attempts = claimed.attempts() + 1;
            Instant now = clock.instant();
            boolean poison = attempts >= MAX_ATTEMPTS;
            transactions.executeWithoutResult(status -> outbox.markFailedAttempt(
                    claimed.event().eventId(), workerId, attempts, poison,
                    now.plus(backoff(attempts)), e.getClass().getSimpleName()));
            log.warn("Outbox delivery failed eventId={} type={} attempts={} poison={} error={}",
                    claimed.event().eventId(), claimed.event().eventType(), attempts, poison, e.getClass().getName());
            return false;
        }
    }

    static Duration backoff(int attempts) {
        return Duration.ofSeconds(Math.min(300, 1L << Math.min(attempts, 8)));
    }

    private static final class LeaseLostException extends RuntimeException {
    }
}
