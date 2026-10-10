package dev.auspex.corehub;

import dev.auspex.corehub.health.HealthReporter;
import dev.auspex.corehub.health.SignalAgeReader;
import io.micrometer.core.instrument.Gauge;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Map;
import java.util.UUID;

import static dev.auspex.corehub.TestFixtures.*;
import static java.util.concurrent.TimeUnit.SECONDS;
import static org.assertj.core.api.Assertions.assertThat;
import static org.awaitility.Awaitility.await;

class HealthReporterIT extends AbstractIT {

    @Autowired
    private SignalAgeReader signalAgeReader;

    @Test
    void signalAgeIsReadFromTheSignalTableAfterARestart() throws Exception {
        publish(SIGNAL_TOPIC, validSignalJson());
        await().atMost(10, SECONDS).until(() -> jdbcTemplate.queryForObject(
                "SELECT count(*) FROM signal_current WHERE event_id = ?",
                Integer.class, UUID.fromString(BASE_EVENT_ID)) == 1);

        // A fresh reporter and registry, as after a core-hub restart: only Postgres knows the signal.
        SimpleMeterRegistry registry = new SimpleMeterRegistry();
        Clock twoDaysLater = Clock.fixed(Instant.parse("2024-06-17T12:00:00Z"), ZoneOffset.UTC);
        new HealthReporter(Map::of, signalAgeReader, registry, twoDaysLater).report();

        Gauge age = registry.find("auspex.source.latest.signal.age").tag("source_type", "biorxiv").gauge();
        assertThat(age).isNotNull();
        // The fixture's ingested_at is 2024-06-15T12:00:00Z.
        assertThat(age.value()).isEqualTo(2 * 86_400.0);
    }
}
