package ru.alfahack.credit.adapters.redis;

import ru.alfahack.credit.ports.ProviderNotImplementedException;
import ru.alfahack.credit.ports.cache.CachePort;

/**
 * Явно отключённый каркас настоящего провайдера: SDK не подключён, успешного фиктивного
 * результата нет. Выбор этого адаптера останавливает запуск. План подключения — adapters/redis/README.md.
 */
public final class RedisCacheAdapter {

    private RedisCacheAdapter() {
    }

    public static CachePort create() {
        throw new ProviderNotImplementedException("RedisCacheAdapter");
    }
}
