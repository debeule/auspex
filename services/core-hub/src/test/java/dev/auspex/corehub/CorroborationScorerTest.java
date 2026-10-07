package dev.auspex.corehub;

import dev.auspex.corehub.corroboration.CorroborationScorer;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Random;

import static org.assertj.core.api.Assertions.assertThat;

class CorroborationScorerTest {

    private static final Instant NOW = Instant.parse("2024-06-15T12:00:00Z");
    private static final Clock FIXED_CLOCK = Clock.fixed(NOW, ZoneOffset.UTC);

    private CorroborationScorer scorer(Clock clock) {
        return new CorroborationScorer(clock);
    }

    @Test
    void test_three_source_types_score_higher_than_two() {
        Instant corroboratedAt = NOW.minusSeconds(60); // very recent — same for both
        double two   = scorer(FIXED_CLOCK).score(2, corroboratedAt);
        double three = scorer(FIXED_CLOCK).score(3, corroboratedAt);
        assertThat(three).isGreaterThan(two);
    }

    @Test
    void test_recent_corroboration_scores_higher_than_stale() {
        int sources = 2;
        Instant recent = NOW.minusSeconds(3_600);                    // 1 hour ago
        Instant stale  = NOW.minusSeconds(89L * 24 * 60 * 60);      // 89 days ago
        double recentScore = scorer(FIXED_CLOCK).score(sources, recent);
        double staleScore  = scorer(FIXED_CLOCK).score(sources, stale);
        assertThat(recentScore).isGreaterThan(staleScore);
    }

    @Test
    void test_score_never_leaves_0_1_range() {
        Random rng = new Random(42L); // fixed seed for reproducibility
        CorroborationScorer s = scorer(FIXED_CLOCK);
        for (int i = 0; i < 10_000; i++) {
            int sources = rng.nextInt(1, 20);
            // corroboratedAt can be anywhere from 2 years ago to "future" (clock jitter)
            long offsetSeconds = (long) (rng.nextGaussian() * 180L * 24 * 60 * 60);
            Instant corroboratedAt = NOW.plusSeconds(offsetSeconds);
            double score = s.score(sources, corroboratedAt);
            assertThat(score)
                    .as("score(%d, %s) = %f", sources, corroboratedAt, score)
                    .isGreaterThanOrEqualTo(0.0)
                    .isLessThanOrEqualTo(1.0);
        }
    }

    @Test
    void test_five_signals_one_source_type_score_below_two_signals_two_source_types() {
        // Diversity must dominate over raw signal count.
        Instant corroboratedAt = NOW.minusSeconds(3_600); // same for both — holds recency constant
        double fiveOneSource = scorer(FIXED_CLOCK).score(1, corroboratedAt);
        double twoTwoSources = scorer(FIXED_CLOCK).score(2, corroboratedAt);
        assertThat(fiveOneSource).isLessThan(twoTwoSources);
    }

    @Test
    void test_scoring_is_a_pure_function_of_its_inputs() {
        CorroborationScorer s = scorer(FIXED_CLOCK);
        Instant t = NOW.minusSeconds(3_600 * 24);
        double first  = s.score(3, t);
        double second = s.score(3, t);
        assertThat(first).isEqualTo(second);
    }
}
