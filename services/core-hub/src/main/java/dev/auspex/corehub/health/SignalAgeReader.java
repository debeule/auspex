package dev.auspex.corehub.health;

import java.time.Instant;
import java.util.Map;

/** When each source's most recent signal was stored, read from the store so it survives restarts. */
@FunctionalInterface
public interface SignalAgeReader {

    Map<String, Instant> latestIngestedAtBySource();
}
