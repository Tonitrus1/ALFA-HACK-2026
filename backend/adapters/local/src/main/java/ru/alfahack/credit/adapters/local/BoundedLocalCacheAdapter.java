package ru.alfahack.credit.adapters.local;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;

import ru.alfahack.credit.ports.PortErrorClass;
import ru.alfahack.credit.ports.PortException;
import ru.alfahack.credit.ports.cache.CacheLookup;
import ru.alfahack.credit.ports.cache.CachePort;

/**
 * Ограниченный in-process TTL-кеш производных данных (LRU по доступу). Попадание только при совпадении
 * sourceVersion и непросроченном TTL; иначе промах и чтение первоисточника. Не общий между репликами.
 */
public class BoundedLocalCacheAdapter implements CachePort {

    private record Entry(long version, byte[] value, Instant expiresAt) {
    }

    private final int maxEntries;
    private final Map<String, Entry> entries;

    public BoundedLocalCacheAdapter(int maxEntries) {
        if (maxEntries < 1) {
            throw new IllegalArgumentException("maxEntries must be positive");
        }
        this.maxEntries = maxEntries;
        this.entries = new LinkedHashMap<>(16, 0.75f, true) {
            @Override
            protected boolean removeEldestEntry(Map.Entry<String, Entry> eldest) {
                return size() > BoundedLocalCacheAdapter.this.maxEntries;
            }
        };
    }

    @Override
    public synchronized CacheLookup get(String key, long sourceVersion, Instant now) {
        Entry entry = entries.get(requireKey(key));
        if (entry == null) {
            return new CacheLookup.Miss();
        }
        if (!now.isBefore(entry.expiresAt()) || entry.version() != sourceVersion) {
            entries.remove(key);
            return new CacheLookup.Miss();
        }
        return new CacheLookup.Hit(entry.value().clone());
    }

    @Override
    public synchronized void put(String key, long version, byte[] value, Instant expiresAt) {
        entries.put(requireKey(key), new Entry(version, value.clone(), expiresAt));
    }

    public synchronized int size() {
        return entries.size();
    }

    private static String requireKey(String key) {
        if (key == null || key.isBlank() || key.length() > 512) {
            throw new PortException(PortErrorClass.INVALID_INPUT, "Invalid cache key");
        }
        return key;
    }
}
