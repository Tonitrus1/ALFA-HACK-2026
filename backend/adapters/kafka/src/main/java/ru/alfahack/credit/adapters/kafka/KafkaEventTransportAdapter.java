package ru.alfahack.credit.adapters.kafka;

import ru.alfahack.credit.ports.ProviderNotImplementedException;
import ru.alfahack.credit.ports.events.EventTransportPort;

/**
 * Явно отключённый каркас настоящего провайдера: SDK не подключён, успешного фиктивного
 * результата нет. Выбор этого адаптера останавливает запуск. План подключения — adapters/kafka/README.md.
 */
public final class KafkaEventTransportAdapter {

    private KafkaEventTransportAdapter() {
    }

    public static EventTransportPort create() {
        throw new ProviderNotImplementedException("KafkaEventTransportAdapter");
    }
}
