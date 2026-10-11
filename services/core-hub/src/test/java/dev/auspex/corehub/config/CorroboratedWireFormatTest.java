package dev.auspex.corehub.config;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import dev.auspex.corehub.corroboration.CorroboratedSignalEvent;
import org.apache.kafka.common.header.internals.RecordHeaders;
import org.apache.kafka.common.serialization.Serializer;
import org.junit.jupiter.api.Test;
import org.springframework.kafka.core.DefaultKafkaProducerFactory;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

/** The corroborated topic is read by the Python strategy runtime, so it follows Invariant 7. */
class CorroboratedWireFormatTest {

    private final ObjectMapper mapper = new JacksonConfig().objectMapper();

    @SuppressWarnings("unchecked")
    private Serializer<Object> corroboratedValueSerializer() {
        KafkaConfig config = new KafkaConfig();
        ReflectionTestUtils.setField(config, "bootstrapServers", "localhost:9092");
        var factory = (DefaultKafkaProducerFactory<Object, Object>)
                config.corroboratedKafkaTemplate(mapper).getProducerFactory();
        return (Serializer<Object>) factory.getValueSerializerSupplier().get();
    }

    @Test
    void test_corroborated_event_is_snake_case_json_with_iso_timestamps_and_no_type_header() throws Exception {
        var event = new CorroboratedSignalEvent(
                "SMN1:Gene",
                "abc",
                List.of(UUID.fromString("00000000-0000-0000-0000-000000000001")),
                2,
                Instant.parse("2026-03-05T14:00:00Z"),
                Instant.parse("2026-03-05T20:00:00.250Z"));
        var headers = new RecordHeaders();

        JsonNode json = mapper.readTree(corroboratedValueSerializer().serialize("auspex.signals.corroborated", headers, event));

        List<String> names = new ArrayList<>();
        json.fieldNames().forEachRemaining(names::add);
        assertThat(names).containsExactlyInAnyOrder(
                "entity_key", "participants_hash", "participant_event_ids",
                "distinct_source_count", "corroborated_at", "first_detected_at");
        assertThat(json.get("corroborated_at").asText()).isEqualTo("2026-03-05T14:00:00Z");
        assertThat(json.get("first_detected_at").asText()).isEqualTo("2026-03-05T20:00:00.250Z");
        assertThat(headers.toArray()).isEmpty();
    }
}
