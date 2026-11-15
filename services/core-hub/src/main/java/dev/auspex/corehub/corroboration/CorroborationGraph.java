package dev.auspex.corehub.corroboration;

import java.time.Instant;
import java.util.Collection;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** The graph reads and writes the corroboration scan and the rules sync need. */
public interface CorroborationGraph {

    /** A {@code GeneTarget} or {@code Mechanism} node by its stored name. */
    record EntityNode(String label, String name) {}

    /** A node and the canonical key to store on it. */
    record KeyedEntity(String label, String name, String key) {}

    /** Up to {@code limit} pending signals published no later than {@code now}, with their write tokens. */
    List<CorroborationScanner.PendingSignal> readPending(Instant now, int limit);

    /** Entity nodes the signals link to that carry no {@code corroboration_key} yet. */
    List<EntityNode> unkeyedEntitiesOf(List<String> eventIds);

    /** Every {@code GeneTarget} and {@code Mechanism} node. */
    List<EntityNode> allEntities();

    void setKeys(List<KeyedEntity> keyed);

    /** The keyed entities the signals link to through {@code TARGETS} or {@code USES_MECHANISM}. */
    Set<EntityRef> entitiesOf(List<String> eventIds);

    /** Each entity's signals published no later than {@code now}, with the tickers they mention. */
    Map<EntityRef, List<CorroborationSignal>> eligibleSignals(Collection<EntityRef> entities, Instant now);

    List<String> allSignalIds();

    /** Marks the signals pending under fresh write tokens. */
    void markPending(List<String> eventIds);

    /** Clears the pending flag on each signal whose write token is still the one read. */
    void clearPending(List<CorroborationScanner.PendingSignal> handled);
}
