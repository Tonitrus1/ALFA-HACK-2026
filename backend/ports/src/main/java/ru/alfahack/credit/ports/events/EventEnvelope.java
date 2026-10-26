package ru.alfahack.credit.ports.events;

/** Конверт события строгих схем credit/ML events v1; payload — JSON по схеме eventType. */
public record EventEnvelope(
        String eventId,
        String eventType,
        String aggregateId,
        long aggregateVersion,
        String traceId,
        String payload) {
}
