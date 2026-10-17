package dev.auspex.corehub;

import com.fasterxml.jackson.databind.node.ObjectNode;
import dev.auspex.corehub.audit.InvalidRawPointerException;
import dev.auspex.corehub.audit.RawAuditService;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.common.header.Header;
import org.junit.jupiter.api.Test;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.bean.override.mockito.MockitoSpyBean;

import java.nio.charset.StandardCharsets;
import java.time.OffsetDateTime;

import static dev.auspex.corehub.TestFixtures.*;
import static java.util.concurrent.TimeUnit.SECONDS;
import static org.assertj.core.api.Assertions.assertThat;
import static org.awaitility.Awaitility.await;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;

/**
 * The raw listener against the pointer the scraper publishes. The audit service is spied on to
 * count deliveries, so the context is its own and discarded after the class.
 */
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_CLASS)
class RawAuditIT extends AbstractIT {

    @MockitoSpyBean
    private RawAuditService rawAuditService;

    @Test
    void test_raw_listener_writes_audit_row_only() throws Exception {
        publish(RAW_TOPIC, validRawJson());

        await().atMost(10, SECONDS).untilAsserted(() -> {
            Integer auditCnt = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM raw_fetch_audit WHERE raw_object_key = ?",
                    Integer.class,
                    validRawField("raw_object_key"));
            assertThat(auditCnt).isEqualTo(1);

            // Raw listener must not write to signal tables
            Integer signalCnt = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM signal_current", Integer.class);
            assertThat(signalCnt).isZero();
        });

        OffsetDateTime retrievedAt = jdbcTemplate.queryForObject(
                "SELECT retrieved_at FROM raw_fetch_audit WHERE raw_object_key = ?",
                OffsetDateTime.class,
                validRawField("raw_object_key"));
        assertThat(retrievedAt).isNotNull();
        assertThat(retrievedAt.isEqual(OffsetDateTime.parse(validRawField("retrieved_at")))).isTrue();

        // And no Neo4j writes
        try (var session = neo4jDriver.session()) {
            long nodeCnt = session.run("MATCH (s:Signal) RETURN count(s) AS cnt")
                    .single().get("cnt").asLong();
            assertThat(nodeCnt).isZero();
        }
    }

    @Test
    void test_invalid_raw_pointer_dead_letters_without_retry() throws Exception {
        ObjectNode pointer = (ObjectNode) objectMapper.readTree(validRawJson());
        pointer.remove("retrieved_at");
        String invalid = pointer.toString();

        publish(RAW_TOPIC, invalid);

        await().atMost(10, SECONDS).untilAsserted(() ->
                assertThat(testDltListener.rawDltRecords()).hasSize(1));

        ConsumerRecord<String, String> dlt = testDltListener.rawDltRecords().getFirst();
        assertThat(dlt.value()).isEqualTo(invalid);
        assertThat(headerValue(dlt, "kafka_dlt-original-topic")).isEqualTo(RAW_TOPIC);
        // The listener's exception is wrapped by the container; the cause is the pointer's own.
        assertThat(headerValue(dlt, "kafka_dlt-exception-cause-fqcn"))
                .isEqualTo(InvalidRawPointerException.class.getName());
        // Retries happen before the record reaches the DLT, so the count is final here.
        verify(rawAuditService, times(1)).record(invalid);
        Integer auditCnt = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM raw_fetch_audit", Integer.class);
        assertThat(auditCnt).isZero();
    }

    private static String headerValue(ConsumerRecord<?, ?> record, String headerName) {
        Header header = record.headers().lastHeader(headerName);
        return header == null ? null : new String(header.value(), StandardCharsets.UTF_8);
    }
}
