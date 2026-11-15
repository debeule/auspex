package dev.auspex.corehub.corroboration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

import java.time.Clock;
import java.util.List;

/**
 * Brings the graph under a rules file on start. When the rules hash stored in
 * {@code corroboration_rules_state} differs from the rules', it keys every entity node, then marks
 * every signal pending under a fresh write token, both in batches, and stores the hash last, so a
 * sync that failed runs again in full. The scan does nothing while the stored hash differs from
 * {@link #rulesInForce()}, so no scan runs on a half-keyed graph; afterwards ordinary scans
 * reconcile every entity under the new rules.
 */
@Component
public class CorroborationRulesSync implements RulesInForce {

    private static final Logger log = LoggerFactory.getLogger(CorroborationRulesSync.class);

    private final EntityRules fileRules;
    private final CorroborationGraph graph;
    private final CorroborationStore store;
    private final Clock clock;
    private final int batchSize;
    private volatile EntityRules inForce;

    public CorroborationRulesSync(EntityRules fileRules, CorroborationGraph graph, CorroborationStore store,
                                  Clock clock, @Value("${corroboration.rules-sync-batch-size}") int batchSize) {
        this.fileRules = fileRules;
        this.graph = graph;
        this.store = store;
        this.clock = clock;
        this.batchSize = batchSize;
        this.inForce = fileRules;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void syncFileRules() {
        sync(fileRules);
    }

    /** Applies {@code rules}; does nothing when their hash is the one last applied. */
    public synchronized void sync(EntityRules rules) {
        inForce = rules;
        if (rules.hash().equals(store.appliedRulesHash())) {
            return;
        }
        List<CorroborationGraph.KeyedEntity> keyed = graph.allEntities().stream()
                .map(n -> new CorroborationGraph.KeyedEntity(n.label(), n.name(), rules.canonicalKey(n.label(), n.name())))
                .toList();
        for (int i = 0; i < keyed.size(); i += batchSize) {
            graph.setKeys(keyed.subList(i, Math.min(keyed.size(), i + batchSize)));
        }
        List<String> signals = graph.allSignalIds();
        for (int i = 0; i < signals.size(); i += batchSize) {
            graph.markPending(signals.subList(i, Math.min(signals.size(), i + batchSize)));
        }
        store.storeAppliedRulesHash(rules.hash(), clock.instant());
        log.info("corroboration rules sync applied rules_hash={} entities={} signals={}",
                rules.hash(), keyed.size(), signals.size());
    }

    @Override
    public EntityRules rulesInForce() {
        return inForce;
    }
}
