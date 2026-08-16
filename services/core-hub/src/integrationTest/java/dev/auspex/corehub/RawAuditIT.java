package dev.auspex.corehub;

import org.junit.jupiter.api.Test;

import static dev.auspex.corehub.TestFixtures.*;
import static java.util.concurrent.TimeUnit.SECONDS;
import static org.assertj.core.api.Assertions.assertThat;
import static org.awaitility.Awaitility.await;

class RawAuditIT extends AbstractIT {

    @Test
    void test_raw_listener_writes_audit_row_only() throws Exception {
        publish(RAW_TOPIC, validRawJson());

        await().atMost(10, SECONDS).untilAsserted(() -> {
            Integer auditCnt = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM raw_fetch_audit WHERE raw_object_key = ?",
                    Integer.class,
                    "raw/biorxiv/ext-contract-001/20240615T120000Z-abcdef12.json");
            assertThat(auditCnt).isEqualTo(1);

            // Raw listener must not write to signal tables
            Integer signalCnt = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM signal_current", Integer.class);
            assertThat(signalCnt).isZero();
        });

        // And no Neo4j writes
        try (var session = neo4jDriver.session()) {
            long nodeCnt = session.run("MATCH (s:Signal) RETURN count(s) AS cnt")
                    .single().get("cnt").asLong();
            assertThat(nodeCnt).isZero();
        }
    }
}
