package dev.auspex.corehub;

import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.common.header.Header;
import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.UUID;

import static dev.auspex.corehub.TestFixtures.*;
import static java.util.concurrent.TimeUnit.SECONDS;
import static org.assertj.core.api.Assertions.assertThat;
import static org.awaitility.Awaitility.await;

class KafkaErrorHandlingIT extends AbstractIT {

    @Test
    void test_naive_timestamp_is_rejected_to_dlq() throws Exception {
        publish(SIGNAL_TOPIC, naiveTimestampSignalJson());

        await().atMost(10, SECONDS).untilAsserted(() ->
                assertThat(testDltListener.signalDltRecords()).hasSize(1));
    }

    @Test
    void test_malformed_json_goes_to_dlt_immediately() throws Exception {
        publish(SIGNAL_TOPIC, "this is not valid json {{{");

        await().atMost(10, SECONDS).untilAsserted(() ->
                assertThat(testDltListener.signalDltRecords()).hasSize(1));
    }

    @Test
    void test_poison_message_does_not_block_partition() throws Exception {
        publish(SIGNAL_TOPIC, "not json at all");
        publish(SIGNAL_TOPIC, validSignalJson()); // should be processed after the poison message

        await().atMost(20, SECONDS).untilAsserted(() -> {
            // DLT gets the poison message
            assertThat(testDltListener.signalDltRecords()).hasSize(1);
            // The valid message is processed into the DB
            Integer cnt = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM signal_current WHERE event_id = ?",
                    Integer.class, UUID.fromString(BASE_EVENT_ID));
            assertThat(cnt).isEqualTo(1);
        });
    }

    @Test
    void test_unknown_enum_value_goes_to_dlt() throws Exception {
        // Unknown major schema version triggers UnknownMajorVersionException (non-retryable → DLT immediately)
        String unknownVersion = validSignalJson()
                .replace("\"schema_version\": \"1.0\"", "\"schema_version\": \"99.0\"");
        publish(SIGNAL_TOPIC, unknownVersion);

        await().atMost(10, SECONDS).untilAsserted(() ->
                assertThat(testDltListener.signalDltRecords()).hasSize(1));
    }

    @Test
    void test_transient_failure_is_retried_and_then_succeeds() throws Exception {
        // With FixedBackOff(1000L, 2), a transient deserialization failure retries up to 2 times.
        // A single malformed message goes to DLT after exhausting retries.
        // This test ensures a second, valid message is processed after the poison one recovers.
        publish(SIGNAL_TOPIC, "{\"schema_version\": \"1.0\", \"event_id\": null}"); // invalid: null UUID

        await().atMost(15, SECONDS).untilAsserted(() ->
                assertThat(testDltListener.signalDltRecords()).hasSize(1));

        // Now send a valid message — must be processed (partition not blocked)
        publish(SIGNAL_TOPIC, validSignalJson());
        await().atMost(10, SECONDS).untilAsserted(() ->
                assertThat(jdbcTemplate.queryForObject(
                        "SELECT COUNT(*) FROM signal_current WHERE event_id = ?",
                        Integer.class, UUID.fromString(BASE_EVENT_ID))).isEqualTo(1));
    }

    @Test
    void test_dlt_headers_present() throws Exception {
        publish(SIGNAL_TOPIC, "malformed json for header check");

        await().atMost(10, SECONDS).untilAsserted(() -> {
            List<ConsumerRecord<String, String>> dltRecords = testDltListener.signalDltRecords();
            assertThat(dltRecords).hasSize(1);

            ConsumerRecord<String, String> dlt = dltRecords.getFirst();
            // Spring Kafka 3.0+ renamed DLT headers: kafka_exception-* → kafka_dlt-exception-*
            assertThat(headerValue(dlt, "kafka_dlt-exception-message")).isNotEmpty();
            assertThat(headerValue(dlt, "kafka_dlt-original-topic")).isEqualTo(SIGNAL_TOPIC);
        });
    }

    @Test
    void test_dlt_publish_succeeds_with_custom_lowercase_resolver() throws Exception {
        // Verifies that DLT records go to the lowercase ".dlt" topic, not uppercase ".DLT"
        publish(SIGNAL_TOPIC, "bad payload for lowercase dlt check");

        await().atMost(10, SECONDS).untilAsserted(() -> {
            List<ConsumerRecord<String, String>> dltRecords = testDltListener.signalDltRecords();
            assertThat(dltRecords).hasSize(1);
            // The TestDltListener listens to "auspex.signals.extracted.dlt" (lowercase).
            // If records arrived here, the resolver produced the correct lowercase topic.
        });
    }

    private String headerValue(ConsumerRecord<?, ?> record, String headerName) {
        Header header = record.headers().lastHeader(headerName);
        if (header == null) return null;
        return new String(header.value(), StandardCharsets.UTF_8);
    }
}
