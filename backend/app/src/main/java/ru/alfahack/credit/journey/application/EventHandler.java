package ru.alfahack.credit.journey.application;

/**
 * Обработчик события из outbox. Вызывается в транзакции доставки; обработчик сам фиксирует inbox
 * (consumer, eventId) атомарно со своим эффектом и игнорирует повтор.
 */
public interface EventHandler {

    String consumer();

    boolean handles(String eventType);

    void handle(EventMessage event);
}
