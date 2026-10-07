package dev.auspex.corehub.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.Test;
import org.springframework.kafka.core.DefaultKafkaConsumerFactory;
import org.springframework.kafka.core.MicrometerConsumerListener;
import org.springframework.test.util.ReflectionTestUtils;

import static org.assertj.core.api.Assertions.assertThat;

class KafkaConfigMetricsTest {

    private final SimpleMeterRegistry registry = new SimpleMeterRegistry();

    private KafkaConfig config() {
        KafkaConfig config = new KafkaConfig();
        ReflectionTestUtils.setField(config, "bootstrapServers", "localhost:9092");
        return config;
    }

    @Test
    void test_signal_consumer_factory_exports_kafka_client_metrics() {
        var factory = (DefaultKafkaConsumerFactory<?, ?>)
                config().signalConsumerFactory(new ObjectMapper(), registry);

        assertThat(factory.getListeners())
                .anyMatch(MicrometerConsumerListener.class::isInstance);
    }

    @Test
    void test_raw_consumer_factory_exports_kafka_client_metrics() {
        var factory = (DefaultKafkaConsumerFactory<?, ?>) config().rawConsumerFactory(registry);

        assertThat(factory.getListeners())
                .anyMatch(MicrometerConsumerListener.class::isInstance);
    }
}
