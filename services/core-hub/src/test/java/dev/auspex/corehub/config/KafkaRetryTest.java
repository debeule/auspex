package dev.auspex.corehub.config;

import org.apache.kafka.clients.consumer.Consumer;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.junit.jupiter.api.Test;
import org.springframework.kafka.listener.ConsumerRecordRecoverer;
import org.springframework.kafka.listener.DefaultErrorHandler;
import org.springframework.kafka.listener.ListenerExecutionFailedException;
import org.springframework.kafka.listener.MessageListenerContainer;
import org.springframework.kafka.support.serializer.DeserializationException;
import org.springframework.util.backoff.BackOffExecution;

import java.nio.charset.StandardCharsets;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;

class KafkaRetryTest {

    @Test
    void transientFailureIsRetriedTwiceWithGrowingBackoff() {
        BackOffExecution execution = KafkaConfig.retryBackOff(5000L, 6.0).start();

        assertThat(execution.nextBackOff()).isEqualTo(5000L);
        assertThat(execution.nextBackOff()).isEqualTo(30000L);
        assertThat(execution.nextBackOff()).isEqualTo(BackOffExecution.STOP);
    }

    @Test
    void deserializationFailureGoesToTheDltWithoutRetry() {
        ConsumerRecordRecoverer recoverer = mock(ConsumerRecordRecoverer.class);
        DefaultErrorHandler handler =
                KafkaConfig.deadLetteringErrorHandler(recoverer, KafkaConfig.retryBackOff(5000L, 6.0));
        ConsumerRecord<String, Object> record =
                new ConsumerRecord<>("auspex.signals.extracted", 0, 7L, "key", null);
        byte[] malformed = "{not json".getBytes(StandardCharsets.UTF_8);
        var failure = new ListenerExecutionFailedException("listener failed",
                new DeserializationException("malformed payload", malformed, false,
                        new IllegalArgumentException("unexpected token")));

        boolean handled = handler.handleOne(
                failure, record, mock(Consumer.class), mock(MessageListenerContainer.class));

        assertThat(handled).isTrue();
        verify(recoverer, times(1)).accept(eq(record), any());
    }
}
