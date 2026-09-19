package dev.auspex.corehub;

import dev.auspex.corehub.persistence.Neo4jWriteService;
import org.junit.jupiter.api.Test;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.bean.override.mockito.MockitoSpyBean;

import java.util.UUID;
import java.util.concurrent.atomic.AtomicInteger;

import static dev.auspex.corehub.TestFixtures.*;
import static java.util.concurrent.TimeUnit.SECONDS;
import static org.assertj.core.api.Assertions.assertThat;
import static org.awaitility.Awaitility.await;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doAnswer;

/**
 * Tests that require fault injection into Neo4jWriteService.
 * Uses @MockitoSpyBean which modifies the Spring context; @DirtiesContext
 * ensures a clean context for subsequent test classes.
 */
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_CLASS)
class FaultInjectionIT extends AbstractIT {

    @MockitoSpyBean
    private Neo4jWriteService neo4jWriteService;

    @Test
    void test_neo4j_failure_prevents_offset_commit_and_redelivery_converges() throws Exception {
        AtomicInteger callCount = new AtomicInteger();
        doAnswer(inv -> {
            if (callCount.incrementAndGet() == 1) {
                throw new RuntimeException("simulated neo4j transient failure");
            }
            return inv.callRealMethod();
        }).when(neo4jWriteService).upsert(any());

        publish(SIGNAL_TOPIC, validSignalJson());

        // After the first failure and retry, the message is processed successfully
        await().atMost(15, SECONDS).untilAsserted(() -> {
            assertThat(callCount.get()).isGreaterThanOrEqualTo(2);
            assertThat(jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM signal_current WHERE event_id = ?",
                    Integer.class, UUID.fromString(BASE_EVENT_ID))).isEqualTo(1);
        });

        // No DLT — message eventually succeeded
        assertThat(testDltListener.signalDltRecords()).isEmpty();
    }

    @Test
    void test_transient_failure_gives_exactly_three_deliveries_then_dlt() throws Exception {
        AtomicInteger callCount = new AtomicInteger();
        doAnswer(inv -> {
            callCount.incrementAndGet();
            throw new RuntimeException("permanent failure for this test");
        }).when(neo4jWriteService).upsert(any());

        publish(SIGNAL_TOPIC, validSignalJson());

        // FixedBackOff(1000L, 2) = 1 attempt + 2 retries = 3 total
        await().atMost(20, SECONDS).untilAsserted(() -> {
            assertThat(callCount.get()).isEqualTo(3);
            assertThat(testDltListener.signalDltRecords()).hasSize(1);
        });
    }
}
