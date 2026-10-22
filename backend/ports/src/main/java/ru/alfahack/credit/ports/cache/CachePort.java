package ru.alfahack.credit.ports.cache;

import java.time.Instant;

/**
 * Кеш производных данных (Redis / CachePort). Локальный провайдер — BoundedLocalCacheAdapter.
 * Кеш никогда не владеет решениями, сессиями, идемпотентностью, правами и финансовыми снимками.
 * Ключ включает namespace, companyId (где применимо), schema, sourceVersion и authEpoch.
 */
public interface CachePort {

    CacheLookup get(String key, long sourceVersion, Instant now);

    void put(String key, long version, byte[] value, Instant expiresAt);
}
