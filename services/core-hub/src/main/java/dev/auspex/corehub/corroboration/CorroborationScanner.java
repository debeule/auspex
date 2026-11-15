package dev.auspex.corehub.corroboration;

import org.springframework.stereotype.Service;

import java.time.Clock;
import java.util.List;
import java.util.UUID;

/**
 * Runs one corroboration scan at the service clock's current time. Every graph write marks its
 * signal pending with a fresh write token in the write's own transaction, so a signal is scanned
 * once its write commits, however late, and once its {@code published_date} has passed. A scanned
 * signal is cleared only by {@link #clearPending}, and only if its token is still the one the scan
 * read.
 */
@Service
public class CorroborationScanner {

    private final CorroborationReconciler reconciler;
    private final CorroborationGraph graph;
    private final Clock clock;

    public CorroborationScanner(CorroborationReconciler reconciler, CorroborationGraph graph, Clock clock) {
        this.reconciler = reconciler;
        this.graph = graph;
        this.clock = clock;
    }

    /** Reconciles the entities of one batch of pending signals; returns the events to publish and the signals read. */
    public ScanResult scan() {
        return reconciler.scan(clock.instant());
    }

    /** Clears the pending flag on each signal whose write token is still the one the scan read. */
    public void clearPending(List<PendingSignal> handled) {
        if (!handled.isEmpty()) {
            graph.clearPending(handled);
        }
    }

    /** A signal read by a scan, with the write token it carried when read. */
    public record PendingSignal(UUID eventId, String writeToken) {}

    public record ScanResult(List<CorroboratedSignalEvent> events, List<PendingSignal> handled) {}
}
