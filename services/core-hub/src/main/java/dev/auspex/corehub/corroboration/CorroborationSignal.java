package dev.auspex.corehub.corroboration;

import java.time.Instant;
import java.util.Set;

/**
 * One signal as the corroboration rules see it. {@code title} may be null; {@code tickers} are the
 * tickers of the companies the signal mentions.
 */
public record CorroborationSignal(String eventId, String sourceType, Instant publishedDate, String title,
                                  Set<String> tickers) {
    public CorroborationSignal {
        tickers = Set.copyOf(tickers);
    }

    public CorroborationSignal(String eventId, String sourceType, Instant publishedDate, String title) {
        this(eventId, sourceType, publishedDate, title, Set.of());
    }
}
