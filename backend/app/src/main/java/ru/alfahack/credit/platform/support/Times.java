package ru.alfahack.credit.platform.support;

import java.time.Clock;
import java.time.Instant;
import java.time.temporal.ChronoUnit;

/** Время с точностью PostgreSQL timestamptz (микросекунды), чтобы повтор возвращал то же значение. */
public final class Times {

    private Times() {
    }

    public static Instant now(Clock clock) {
        return clock.instant().truncatedTo(ChronoUnit.MICROS);
    }
}
