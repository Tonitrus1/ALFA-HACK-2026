package ru.alfahack.credit.journey.application;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;

/** Конверт строгого события credit-events v1 (schemaVersion 1). */
public record EventMessage(
        UUID eventId,
        String eventType,
        int schemaVersion,
        String aggregateId,
        long aggregateVersion,
        String applicationId,
        Instant occurredAt,
        String correlationId,
        String causationId,
        Map<String, Object> payload) {

    public EventMessage {
        payload = Map.copyOf(payload);
    }

    public String payloadString(String field) {
        Object value = payload.get(field);
        return value == null ? null : value.toString();
    }

    public long payloadLong(String field) {
        return ((Number) payload.get(field)).longValue();
    }
}
