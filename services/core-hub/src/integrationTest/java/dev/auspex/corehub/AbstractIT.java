package dev.auspex.corehub;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.neo4j.driver.Driver;
import org.neo4j.driver.Session;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.test.context.EmbeddedKafka;
import org.springframework.test.context.ActiveProfiles;

import java.util.concurrent.ExecutionException;

/**
 * Base class for all container-backed integration tests.
 * All subclasses share one Spring context (annotation config is identical).
 * Containers (Postgres, Neo4j) are singleton Spring beans; embedded Kafka
 * is shared via EmbeddedKafka's internal broker.
 */
@SpringBootTest
@ActiveProfiles("test")
@EmbeddedKafka(
        partitions = 1,
        bootstrapServersProperty = "spring.kafka.bootstrap-servers",
        topics = {
                "auspex.signals.extracted",
                "auspex.signals.extracted.dlt",
                "auspex.raw.ingested",
                "auspex.raw.ingested.dlt",
                "auspex.signals.corroborated"
        }
)
@Import(TestContainersConfig.class)
public abstract class AbstractIT {

    @Autowired
    protected JdbcTemplate jdbcTemplate;

    @Autowired
    protected Driver neo4jDriver;

    @Autowired
    protected KafkaTemplate<Object, Object> kafkaTemplate;

    @Autowired
    protected ObjectMapper objectMapper;

    @Autowired
    protected TestDltListener testDltListener;

    @Autowired
    protected TestCorroboratedListener testCorroboratedListener;

    @BeforeEach
    protected void cleanState() throws Exception {
        jdbcTemplate.execute(
                "TRUNCATE raw_fetch_audit, signal_current, signal_extraction_history, source_observation, corroboration, corroboration_state RESTART IDENTITY CASCADE");
        try (Session session = neo4jDriver.session()) {
            session.run("MATCH (n) WHERE NOT n:GraphSchema DETACH DELETE n");
        }
        testDltListener.clear();
        testCorroboratedListener.clear();
    }

    protected void publish(String topic, String payload) throws ExecutionException, InterruptedException {
        kafkaTemplate.send(topic, payload).get();
    }
}
