package ru.alfahack.credit.adapters.local;

import java.util.ArrayList;
import java.util.List;

import ru.alfahack.credit.ports.events.DeliveryReceipt;
import ru.alfahack.credit.ports.events.EventEnvelope;
import ru.alfahack.credit.ports.events.EventSink;
import ru.alfahack.credit.ports.events.EventTransportPort;
import ru.alfahack.credit.ports.events.InboxAck;
import ru.alfahack.credit.ports.events.OutboxBatch;

/**
 * Локальный транспорт local-mvp: закоммиченные записи PostgreSQL outbox передаются тем же in-process
 * обработчикам (inbox фиксируется атомарно с эффектом на стороне обработчика). Kafka-протокол не эмулируется.
 * Выбор партии (SKIP LOCKED, lease, backoff) выполняет dispatcher владельца outbox.
 */
public class PostgresOutboxTransportAdapter implements EventTransportPort {

    private final EventSink sink;

    public PostgresOutboxTransportAdapter(EventSink sink) {
        this.sink = sink;
    }

    @Override
    public DeliveryReceipt dispatch(OutboxBatch committedOutboxBatch) {
        List<String> delivered = new ArrayList<>();
        List<String> failed = new ArrayList<>();
        for (EventEnvelope event : committedOutboxBatch.events()) {
            try {
                sink.deliver(event);
                delivered.add(event.eventId());
            } catch (RuntimeException e) {
                failed.add(event.eventId());
            }
        }
        return new DeliveryReceipt(delivered, failed);
    }

    @Override
    public InboxAck consume(EventEnvelope eventEnvelope) {
        return sink.deliver(eventEnvelope);
    }
}
