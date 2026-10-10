package dev.auspex.corehub.kafka;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.config.KafkaListenerEndpointRegistry;
import org.springframework.kafka.listener.MessageListenerContainer;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * Pauses the signal and raw listeners while Postgres or Neo4j is unreachable and resumes them
 * when both are back, so an outage holds records on the topic instead of spending their retries
 * and dead-lettering them.
 */
@Component
public class StoreAvailabilityGuard {

    private static final Logger log = LoggerFactory.getLogger(StoreAvailabilityGuard.class);
    private static final List<String> GUARDED_CONTAINERS =
            List.of(SignalListener.CONTAINER_ID, RawListener.CONTAINER_ID);

    private final KafkaListenerEndpointRegistry registry;
    private final List<StoreProbe> probes;
    private boolean paused;

    public StoreAvailabilityGuard(KafkaListenerEndpointRegistry registry, List<StoreProbe> probes) {
        this.registry = registry;
        this.probes = List.copyOf(probes);
    }

    @Scheduled(fixedDelayString = "${auspex.kafka.store-check-interval-ms:5000}")
    public synchronized void check() {
        List<String> down = probes.stream().filter(probe -> !isUp(probe)).map(StoreProbe::name).toList();
        if (!down.isEmpty() && !paused) {
            log.warn("pausing listeners: stores unreachable={}", down);
            GUARDED_CONTAINERS.forEach(id -> container(id).pause());
            paused = true;
        } else if (down.isEmpty() && paused) {
            log.warn("resuming listeners: all stores reachable");
            GUARDED_CONTAINERS.forEach(id -> container(id).resume());
            paused = false;
        }
    }

    private static boolean isUp(StoreProbe probe) {
        try {
            return probe.isUp();
        } catch (RuntimeException e) {
            log.debug("store probe failed store={} error={}", probe.name(), e.toString());
            return false;
        }
    }

    private MessageListenerContainer container(String id) {
        MessageListenerContainer container = registry.getListenerContainer(id);
        if (container == null) {
            throw new IllegalStateException("no listener container with id " + id);
        }
        return container;
    }
}
