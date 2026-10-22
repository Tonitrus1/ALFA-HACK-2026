package ru.alfahack.credit.ports.events;

/**
 * Транспорт событий (Kafka / EventTransportPort). Локальный провайдер — PostgresOutboxTransportAdapter.
 * Доставка at-least-once; inbox и бизнес-эффект фиксируются атомарно; outbox остаётся источником.
 */
public interface EventTransportPort {

    DeliveryReceipt dispatch(OutboxBatch committedOutboxBatch);

    InboxAck consume(EventEnvelope eventEnvelope);
}
