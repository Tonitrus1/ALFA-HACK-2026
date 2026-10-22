package ru.alfahack.credit.ports.events;

/**
 * Приёмная сторона транспорта внутри процесса: передаёт конверт обработчикам потребителя.
 * Возвращает подтверждение только после commit inbox; исключение — доставка не состоялась.
 */
@FunctionalInterface
public interface EventSink {

    InboxAck deliver(EventEnvelope envelope);
}
