package dev.auspex.corehub.corroboration;

import org.springframework.stereotype.Component;

import java.time.Clock;
import java.time.Instant;

/**
 * Pure scoring function for corroboration strength.
 * Score = 0.7 * diversity_factor + 0.3 * recency_factor, clamped to [0, 1].
 *
 * diversity_factor = min(1, (distinctSourceCount - 1) / 4)
 *   — 2 sources → 0.25, 3 → 0.50, 4 → 0.75, 5+ → 1.00
 *
 * recency_factor = max(0, 1 - age_seconds / 90_days)
 *   — vanishes beyond the corroboration window.
 */
@Component
public class CorroborationScorer {

    private static final double DIVERSITY_WEIGHT = 0.7;
    private static final double RECENCY_WEIGHT = 0.3;
    private static final double MAX_DIVERSITY_DELTA = 4.0; // 5+ distinct sources = full score
    private static final long RECENCY_WINDOW_SECONDS = 90L * 24 * 60 * 60;

    private final Clock clock;

    public CorroborationScorer(Clock clock) {
        this.clock = clock;
    }

    public double score(int distinctSourceCount, Instant corroboratedAt) {
        double diversityFactor = Math.min(1.0, (distinctSourceCount - 1.0) / MAX_DIVERSITY_DELTA);

        long ageSeconds = clock.instant().getEpochSecond() - corroboratedAt.getEpochSecond();
        double recencyFactor = Math.max(0.0, 1.0 - (double) ageSeconds / RECENCY_WINDOW_SECONDS);

        double raw = DIVERSITY_WEIGHT * diversityFactor + RECENCY_WEIGHT * recencyFactor;
        return Math.min(1.0, Math.max(0.0, raw));
    }
}
