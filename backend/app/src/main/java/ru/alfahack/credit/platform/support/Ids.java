package ru.alfahack.credit.platform.support;

import java.util.UUID;

/** Непрозрачные идентификаторы без ПДн. */
public final class Ids {

    private Ids() {
    }

    public static String newId() {
        return UUID.randomUUID().toString();
    }

    public static UUID newEventId() {
        return UUID.randomUUID();
    }
}
