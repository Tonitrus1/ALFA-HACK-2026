package ru.alfahack.credit.ports.cache;

/** HitOrMiss из каталога. Промах или отказ — читать тот же разрешённый первоисточник. */
public sealed interface CacheLookup {

    record Hit(byte[] value) implements CacheLookup {
    }

    record Miss() implements CacheLookup {
    }
}
