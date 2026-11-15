package dev.auspex.corehub;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneId;
import java.time.ZoneOffset;

/** The service clock in tests: the system clock until a test sets it; reset before every test. */
public final class MutableClock extends Clock {

    private volatile Instant fixed;

    public void set(Instant instant) {
        fixed = instant;
    }

    public void reset() {
        fixed = null;
    }

    @Override
    public ZoneId getZone() {
        return ZoneOffset.UTC;
    }

    @Override
    public Clock withZone(ZoneId zone) {
        return this;
    }

    @Override
    public Instant instant() {
        Instant now = fixed;
        return now != null ? now : Instant.now();
    }
}
