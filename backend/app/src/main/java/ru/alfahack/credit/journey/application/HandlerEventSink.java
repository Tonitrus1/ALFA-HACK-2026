package ru.alfahack.credit.journey.application;

import java.util.List;

import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import tools.jackson.databind.json.JsonMapper;

import ru.alfahack.credit.ports.events.EventEnvelope;
import ru.alfahack.credit.ports.events.EventSink;
import ru.alfahack.credit.ports.events.InboxAck;

/**
 * Приёмник локального транспорта: восстанавливает строгий конверт и вызывает обработчики потребителей
 * в транзакции доставки. Каждый обработчик фиксирует свой inbox атомарно с эффектом.
 */
@Component
class HandlerEventSink implements EventSink {

    private final List<EventHandler> handlers;
    private final JsonMapper json;

    HandlerEventSink(List<EventHandler> handlers, JsonMapper json) {
        this.handlers = List.copyOf(handlers);
        this.json = json;
    }

    @Override
    @Transactional(propagation = Propagation.MANDATORY)
    public InboxAck deliver(EventEnvelope envelope) {
        EventMessage event = json.readValue(envelope.payload(), EventMessage.class);
        for (EventHandler handler : handlers) {
            if (handler.handles(event.eventType())) {
                handler.handle(event);
            }
        }
        return new InboxAck(envelope.eventId(), false);
    }
}
