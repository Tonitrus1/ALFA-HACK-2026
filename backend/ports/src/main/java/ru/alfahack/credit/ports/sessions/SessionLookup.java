package ru.alfahack.credit.ports.sessions;

/** SessionOrMissing из каталога. */
public sealed interface SessionLookup {

    record Found(Session session) implements SessionLookup {
    }

    record Missing() implements SessionLookup {
    }
}
