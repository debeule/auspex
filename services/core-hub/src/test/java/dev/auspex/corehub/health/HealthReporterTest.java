package dev.auspex.corehub.health;

import io.micrometer.prometheusmetrics.PrometheusConfig;
import io.micrometer.prometheusmetrics.PrometheusMeterRegistry;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.assertThat;

class HealthReporterTest {

    private static final Instant NOW = Instant.parse("2026-10-10T07:00:00Z");

    private final PrometheusMeterRegistry registry = new PrometheusMeterRegistry(PrometheusConfig.DEFAULT);
    private final Map<String, Long> depths = new HashMap<>();
    private final Map<String, Instant> latest = new HashMap<>();
    private final AtomicReference<Instant> now = new AtomicReference<>(NOW);

    private final Clock clock = new Clock() {
        @Override
        public ZoneOffset getZone() { return ZoneOffset.UTC; }

        @Override
        public Clock withZone(java.time.ZoneId zone) { return this; }

        @Override
        public Instant instant() { return now.get(); }
    };

    private final HealthReporter reporter =
            new HealthReporter(() -> Map.copyOf(depths), () -> Map.copyOf(latest), registry, clock);

    private double sample(String name, String label, String value) {
        String prefix = name + "{" + label + "=\"" + value + "\"";
        return registry.scrape().lines()
                .filter(line -> line.startsWith(prefix))
                .mapToDouble(line -> Double.parseDouble(line.substring(line.lastIndexOf(' ') + 1)))
                .findFirst()
                .orElseThrow(() -> new AssertionError("no sample " + prefix + " in\n" + registry.scrape()));
    }

    @Test
    void healthReporterExportsDltDepthPerTopic() {
        depths.put("auspex.signals.extracted.dlt", 3L);
        depths.put("auspex.raw.ingested.dlt", 0L);

        reporter.report();

        assertThat(sample("auspex_dlt_depth", "topic", "auspex.signals.extracted.dlt")).isEqualTo(3.0);
        assertThat(sample("auspex_dlt_depth", "topic", "auspex.raw.ingested.dlt")).isEqualTo(0.0);

        // A replay empties the topic: the next report lowers the gauge.
        depths.put("auspex.signals.extracted.dlt", 0L);
        reporter.report();

        assertThat(sample("auspex_dlt_depth", "topic", "auspex.signals.extracted.dlt")).isEqualTo(0.0);
    }

    @Test
    void healthReporterExportsSignalAgePerSourceFromPostgres() {
        latest.put("biorxiv", NOW.minus(Duration.ofHours(2)));
        latest.put("edgar", NOW.minus(Duration.ofDays(6)));

        reporter.report();

        assertThat(sample("auspex_source_latest_signal_age_seconds", "source_type", "biorxiv"))
                .isEqualTo(7_200.0);
        assertThat(sample("auspex_source_latest_signal_age_seconds", "source_type", "edgar"))
                .isEqualTo(6 * 86_400.0);

        // The age keeps growing between reports, so a stalled reader cannot freeze it.
        now.set(NOW.plus(Duration.ofHours(1)));

        assertThat(sample("auspex_source_latest_signal_age_seconds", "source_type", "biorxiv"))
                .isEqualTo(10_800.0);
    }
}
