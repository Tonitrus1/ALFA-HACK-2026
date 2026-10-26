package ru.alfahack.credit.journey.application;

import java.time.Clock;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import ru.alfahack.credit.journey.infrastructure.OutboxRepository;

/** Запись события в outbox в той же транзакции, что и бизнес-эффект. */
@Service
public class Outbox {

    private final OutboxRepository outbox;
    private final Clock clock;

    public Outbox(OutboxRepository outbox, Clock clock) {
        this.outbox = outbox;
        this.clock = clock;
    }

    @Transactional(propagation = Propagation.MANDATORY)
    public void append(EventMessage event) {
        outbox.insert(event, clock.instant());
    }
}
