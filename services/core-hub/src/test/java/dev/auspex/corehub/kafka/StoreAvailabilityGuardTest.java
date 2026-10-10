package dev.auspex.corehub.kafka;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.kafka.config.KafkaListenerEndpointRegistry;
import org.springframework.kafka.listener.MessageListenerContainer;

import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class StoreAvailabilityGuardTest {

    private final KafkaListenerEndpointRegistry registry = mock(KafkaListenerEndpointRegistry.class);
    private final MessageListenerContainer signalContainer = mock(MessageListenerContainer.class);
    private final MessageListenerContainer rawContainer = mock(MessageListenerContainer.class);
    private final AtomicBoolean postgresUp = new AtomicBoolean(true);
    private final AtomicBoolean neo4jUp = new AtomicBoolean(true);

    private StoreAvailabilityGuard guard;

    @BeforeEach
    void setUp() {
        when(registry.getListenerContainer(SignalListener.CONTAINER_ID)).thenReturn(signalContainer);
        when(registry.getListenerContainer(RawListener.CONTAINER_ID)).thenReturn(rawContainer);
        guard = new StoreAvailabilityGuard(registry, List.of(
                probe("postgres", postgresUp),
                probe("neo4j", neo4jUp)));
    }

    private static StoreProbe probe(String name, AtomicBoolean up) {
        return new StoreProbe() {
            @Override
            public String name() { return name; }

            @Override
            public boolean isUp() {
                if (!up.get()) {
                    throw new IllegalStateException(name + " unreachable");
                }
                return true;
            }
        };
    }

    @Test
    void listenersPauseWhenNeo4jIsDown() {
        neo4jUp.set(false);

        guard.check();

        verify(signalContainer).pause();
        verify(rawContainer).pause();
    }

    @Test
    void listenersPauseWhenPostgresIsDown() {
        postgresUp.set(false);

        guard.check();

        verify(signalContainer).pause();
        verify(rawContainer).pause();
    }

    @Test
    void listenersResumeOnlyWhenBothStoresAreUp() {
        postgresUp.set(false);
        neo4jUp.set(false);
        guard.check();

        neo4jUp.set(true);
        guard.check();
        verify(signalContainer, never()).resume();
        verify(rawContainer, never()).resume();

        postgresUp.set(true);
        guard.check();
        verify(signalContainer).resume();
        verify(rawContainer).resume();
    }
}
