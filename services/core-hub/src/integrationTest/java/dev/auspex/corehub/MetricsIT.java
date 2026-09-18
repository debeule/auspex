package dev.auspex.corehub;

import io.micrometer.core.instrument.MeterRegistry;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.test.web.servlet.MockMvc;

import java.util.concurrent.TimeUnit;

import static org.assertj.core.api.Assertions.assertThat;
import static org.awaitility.Awaitility.await;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@AutoConfigureMockMvc
class MetricsIT extends AbstractIT {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private MeterRegistry meterRegistry;

    @Test
    void test_prometheus_endpoint_returns_200() throws Exception {
        mockMvc.perform(get("/actuator/prometheus"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith("text/plain"));
    }

    @Test
    void test_kafka_consumer_lag_metric_is_registered() {
        // Kafka consumer lag is registered by the Micrometer Kafka binder after
        // the consumer receives its first partition assignment.
        await().atMost(30, TimeUnit.SECONDS).untilAsserted(() ->
                assertThat(meterRegistry.find("kafka.consumer.records.lag").gauge())
                        .isNotNull()
        );
    }
}
