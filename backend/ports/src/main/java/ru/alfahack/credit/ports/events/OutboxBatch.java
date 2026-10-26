package ru.alfahack.credit.ports.events;

import java.util.List;

/** Пакет уже закоммиченных записей outbox. */
public record OutboxBatch(List<EventEnvelope> events) {

    public OutboxBatch {
        events = List.copyOf(events);
    }
}
