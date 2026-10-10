package dev.auspex.corehub;

import dev.auspex.corehub.kafka.Neo4jStoreProbe;
import dev.auspex.corehub.kafka.SignalListener;
import dev.auspex.corehub.persistence.Neo4jWriteService;
import org.apache.kafka.clients.consumer.Consumer;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.common.TopicPartition;
import org.apache.kafka.common.header.Header;
import org.apache.kafka.common.header.internals.RecordHeader;
import org.apache.kafka.common.serialization.ByteArrayDeserializer;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.neo4j.driver.Session;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.kafka.config.KafkaListenerEndpointRegistry;
import org.springframework.kafka.core.DefaultKafkaConsumerFactory;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.bean.override.mockito.MockitoSpyBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.WebApplicationContext;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicBoolean;

import static dev.auspex.corehub.TestFixtures.*;
import static java.util.concurrent.TimeUnit.SECONDS;
import static org.assertj.core.api.Assertions.assertThat;
import static org.awaitility.Awaitility.await;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doAnswer;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Store outages and dead-letter replay. Neo4j failures are injected through spies, so the context
 * is its own and discarded after the class.
 */
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_CLASS)
class DeadLetterRecoveryIT extends AbstractIT {

    private static final String SIGNAL_DLT = "auspex.signals.extracted.dlt";

    @MockitoSpyBean
    private Neo4jWriteService neo4jWriteService;

    @MockitoSpyBean
    private Neo4jStoreProbe neo4jStoreProbe;

    @Autowired
    private KafkaListenerEndpointRegistry listenerRegistry;

    @Autowired
    private WebApplicationContext webApplicationContext;

    @Value("${auspex.api.write-token}")
    private String writeToken;

    @Value("${spring.kafka.bootstrap-servers}")
    private String bootstrapServers;

    private final AtomicBoolean neo4jDown = new AtomicBoolean(false);
    private final AtomicBoolean writesFail = new AtomicBoolean(false);
    private MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        mockMvc = MockMvcBuilders.webAppContextSetup(webApplicationContext).build();
        neo4jDown.set(false);
        writesFail.set(false);
        doAnswer(inv -> !neo4jDown.get() && (boolean) inv.callRealMethod()).when(neo4jStoreProbe).isUp();
        doAnswer(inv -> {
            if (neo4jDown.get() || writesFail.get()) {
                throw new IllegalStateException("simulated neo4j outage");
            }
            return inv.callRealMethod();
        }).when(neo4jWriteService).upsert(any());
    }

    @Test
    void recordConsumedDuringANeo4jOutageIsStoredAfterRecovery() throws Exception {
        String eventId = UUID.randomUUID().toString();
        neo4jDown.set(true);
        await().atMost(10, SECONDS).until(
                () -> listenerRegistry.getListenerContainer(SignalListener.CONTAINER_ID).isContainerPaused());

        publish(SIGNAL_TOPIC, signalJson(eventId));

        // Paused: the record waits on the topic instead of spending its three deliveries.
        await().during(4, SECONDS).atMost(6, SECONDS).untilAsserted(() -> {
            assertThat(signalRows(eventId)).isZero();
            assertThat(testDltListener.signalDltRecords()).isEmpty();
        });

        neo4jDown.set(false);

        await().atMost(20, SECONDS).untilAsserted(() -> assertThat(signalRows(eventId)).isEqualTo(1));
        assertThat(testDltListener.signalDltRecords()).isEmpty();
    }

    @Test
    void replayRepublishesDeadLettersToTheSourceTopicWithKeyAndHeaders() throws Exception {
        String eventId = UUID.randomUUID().toString();
        deadLetter(eventId);

        try (Consumer<byte[], byte[]> sourceConsumer = sourceTopicConsumerAtEnd()) {
            replay().andExpect(jsonPath("$.replayed").value(1));

            List<ConsumerRecord<byte[], byte[]>> republished = pollFor(sourceConsumer, eventId);
            assertThat(republished).hasSize(1);
            ConsumerRecord<byte[], byte[]> record = republished.getFirst();
            assertThat(new String(record.key(), StandardCharsets.UTF_8)).isEqualTo(eventId);
            assertThat(headerValue(record, "schema_version")).isEqualTo("1.0");
            assertThat(record.headers().toArray())
                    .extracting(Header::key)
                    .noneMatch(key -> key.startsWith("kafka_dlt-") || key.endsWith("TypeId__"));
        }

        await().atMost(20, SECONDS).untilAsserted(() -> assertThat(signalRows(eventId)).isEqualTo(1));
    }

    @Test
    void replayDoesNotRepublishARecordTwice() throws Exception {
        deadLetter(UUID.randomUUID().toString());

        replay().andExpect(jsonPath("$.replayed").value(1));
        replay().andExpect(jsonPath("$.replayed").value(0));
    }

    @Test
    void replayedSignalIsStoredOnce() throws Exception {
        String eventId = UUID.randomUUID().toString();
        String json = signalJson(eventId);
        publishKeyed(eventId, json);
        await().atMost(20, SECONDS).untilAsserted(() -> assertThat(signalRows(eventId)).isEqualTo(1));

        writesFail.set(true);
        publishKeyed(eventId, json);
        await().atMost(20, SECONDS).untilAsserted(
                () -> assertThat(testDltListener.signalDltRecords()).hasSize(1));
        writesFail.set(false);

        replay().andExpect(jsonPath("$.replayed").value(1));

        // 1 stored + 3 failed deliveries + 1 replayed; the natural keys keep one row and one node.
        await().atMost(20, SECONDS).untilAsserted(
                () -> assertThat(graphWriteCalls(eventId)).isEqualTo(5));
        assertThat(signalRows(eventId)).isEqualTo(1);
        assertThat(signalNodes(eventId)).isEqualTo(1);
    }

    @Test
    void replayRequiresTheWriteToken() throws Exception {
        String eventId = UUID.randomUUID().toString();
        deadLetter(eventId);

        mockMvc.perform(post("/api/dlt/{topic}/replay", SIGNAL_DLT))
                .andExpect(status().isUnauthorized());
        assertThat(signalRows(eventId)).isZero();

        replay().andExpect(jsonPath("$.replayed").value(1));
    }

    private ResultActions replay() throws Exception {
        return mockMvc.perform(post("/api/dlt/{topic}/replay", SIGNAL_DLT)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + writeToken))
                .andExpect(status().isOk());
    }

    /** Publishes a signal while Neo4j writes fail and waits for its dead letter. */
    private void deadLetter(String eventId) throws Exception {
        writesFail.set(true);
        publishKeyed(eventId, signalJson(eventId));
        await().atMost(20, SECONDS).untilAsserted(
                () -> assertThat(testDltListener.signalDltRecords()).hasSize(1));
        writesFail.set(false);
    }

    private void publishKeyed(String key, String json) throws Exception {
        var record = new ProducerRecord<Object, Object>(SIGNAL_TOPIC, null, key, json,
                List.of(new RecordHeader("schema_version", "1.0".getBytes(StandardCharsets.UTF_8))));
        kafkaTemplate.send(record).get();
    }

    private static String signalJson(String eventId) {
        return validSignalJson()
                .replace(BASE_EVENT_ID, eventId)
                .replace(BASE_EXTRACTION_ID, UUID.randomUUID().toString());
    }

    private Consumer<byte[], byte[]> sourceTopicConsumerAtEnd() {
        Consumer<byte[], byte[]> consumer = new DefaultKafkaConsumerFactory<>(
                Map.<String, Object>of(
                        ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers,
                        ConsumerConfig.GROUP_ID_CONFIG, "test-replay-observer-" + UUID.randomUUID(),
                        ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG, false),
                new ByteArrayDeserializer(), new ByteArrayDeserializer()).createConsumer();
        TopicPartition partition = new TopicPartition(SIGNAL_TOPIC, 0);
        consumer.assign(List.of(partition));
        consumer.seekToEnd(List.of(partition));
        consumer.position(partition);
        return consumer;
    }

    private static List<ConsumerRecord<byte[], byte[]>> pollFor(Consumer<byte[], byte[]> consumer, String eventId) {
        List<ConsumerRecord<byte[], byte[]>> matching = new ArrayList<>();
        await().atMost(10, SECONDS).until(() -> {
            for (ConsumerRecord<byte[], byte[]> record : consumer.poll(Duration.ofMillis(200))) {
                if (new String(record.value(), StandardCharsets.UTF_8).contains(eventId)) {
                    matching.add(record);
                }
            }
            return !matching.isEmpty();
        });
        return matching;
    }

    private static String headerValue(ConsumerRecord<byte[], byte[]> record, String key) {
        Header header = record.headers().lastHeader(key);
        return header == null ? null : new String(header.value(), StandardCharsets.UTF_8);
    }

    private int signalRows(String eventId) {
        return jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM signal_current WHERE event_id = ?", Integer.class, UUID.fromString(eventId));
    }

    private long signalNodes(String eventId) {
        try (Session session = neo4jDriver.session()) {
            return session.run("MATCH (s:Signal {event_id: $eid}) RETURN count(s) AS n", Map.of("eid", eventId))
                    .single().get("n").asLong();
        }
    }

    /** Successful and failed calls to the graph write for this event. */
    private long graphWriteCalls(String eventId) {
        return org.mockito.Mockito.mockingDetails(neo4jWriteService).getInvocations().stream()
                .filter(inv -> inv.getMethod().getName().equals("upsert"))
                .filter(inv -> inv.getArgument(0).toString().contains(eventId))
                .count();
    }
}
