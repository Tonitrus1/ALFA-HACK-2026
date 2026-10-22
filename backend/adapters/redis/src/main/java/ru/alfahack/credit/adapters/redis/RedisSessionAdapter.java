package ru.alfahack.credit.adapters.redis;

import ru.alfahack.credit.ports.ProviderNotImplementedException;
import ru.alfahack.credit.ports.sessions.SessionStorePort;

/**
 * Явно отключённый каркас настоящего провайдера: SDK не подключён, успешного фиктивного
 * результата нет. Выбор этого адаптера останавливает запуск. План подключения — adapters/redis/README.md.
 */
public final class RedisSessionAdapter {

    private RedisSessionAdapter() {
    }

    public static SessionStorePort create() {
        throw new ProviderNotImplementedException("RedisSessionAdapter");
    }
}
