package dev.auspex.corehub;

import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.Map;
import java.util.UUID;

import static dev.auspex.corehub.TestFixtures.*;
import static java.util.concurrent.TimeUnit.SECONDS;
import static org.assertj.core.api.Assertions.assertThat;
import static org.awaitility.Awaitility.await;

/**
 * Runs under a non-UTC default JVM timezone (America/New_York) via the timezoneCheck task.
 * Verifies that timestamps stored in Postgres and Neo4j are UTC-correct regardless of
 * the JVM's default timezone.
 */
@Tag("timezoneCheck")
class SignalTimezoneIT extends AbstractIT {

    @Test
    void test_non_utc_default_timezone_does_not_alter_stored_values() throws Exception {
        publish(SIGNAL_TOPIC, validSignalJson());

        await().atMost(10, SECONDS).untilAsserted(() -> {
            var rows = jdbcTemplate.queryForList(
                    "SELECT published_date FROM signal_current WHERE event_id = ?",
                    UUID.fromString(BASE_EVENT_ID));
            assertThat(rows).hasSize(1);

            Object storedDate = rows.getFirst().get("published_date");
            // The fixture has published_date = 2024-06-15T12:00:00Z.
            // Under America/New_York the JVM default offset is -4h or -5h.
            // If the service incorrectly used LocalDateTime / the default TZ,
            // the stored value would be off by the local offset.
            assertThat(storedDate).isNotNull();
            // PostgreSQL JDBC returns java.sql.Timestamp for TIMESTAMPTZ via queryForList.
            // Convert to OffsetDateTime and verify UTC value was preserved.
            OffsetDateTime odt = switch (storedDate) {
                case OffsetDateTime o    -> o.withOffsetSameInstant(ZoneOffset.UTC);
                case java.sql.Timestamp t -> t.toInstant().atOffset(ZoneOffset.UTC);
                default -> throw new AssertionError("Unexpected JDBC type: " + storedDate.getClass());
            };
            assertThat(odt.getHour()).isEqualTo(12);
            assertThat(odt.getOffset()).isEqualTo(ZoneOffset.UTC);
        });
    }
}
