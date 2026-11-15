package dev.auspex.corehub.corroboration;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.TreeSet;
import java.util.UUID;

/**
 * Makes the {@code corroboration} table agree with the episodes of every entity a batch of pending
 * signals touches, and returns the events to publish. Nothing is cleared here: the caller sends the
 * events, commits, and then clears the signals read.
 *
 * <p>For each entity the scan builds the episodes of the entity scope and, unless the entity is
 * broad, of each ticker scope, from the entity's signals published by {@code now}. An episode with
 * no row is inserted; a superseded row an episode produces again is made live; a live row no
 * episode produces is superseded by the hash of the episode in its scope that shares a participant
 * with it, or by the literal {@code rules}. A live row with no {@code excluded_reason} and no
 * {@code published_at} is returned for publication and marked published in the same transaction.
 */
@Service
public class CorroborationReconciler {

    static final String SUPERSEDED_BY_RULES = "rules";

    private final CorroborationGraph graph;
    private final CorroborationStore store;
    private final RulesInForce rules;
    private final int scanBatchSize;
    private final int degreeCap;

    public CorroborationReconciler(CorroborationGraph graph, CorroborationStore store, RulesInForce rules,
                                   @Value("${corroboration.scan-batch-size}") int scanBatchSize,
                                   @Value("${corroboration.degree-cap:500}") int degreeCap) {
        this.graph = graph;
        this.store = store;
        this.rules = rules;
        this.scanBatchSize = scanBatchSize;
        this.degreeCap = degreeCap;
    }

    public CorroborationScanner.ScanResult scan(Instant now) {
        EntityRules entityRules = rules.rulesInForce();
        if (!entityRules.hash().equals(store.appliedRulesHash())) {
            return new CorroborationScanner.ScanResult(List.of(), List.of());
        }
        List<CorroborationScanner.PendingSignal> pending = graph.readPending(now, scanBatchSize);
        if (pending.isEmpty()) {
            return new CorroborationScanner.ScanResult(List.of(), List.of());
        }
        List<String> ids = pending.stream().map(p -> p.eventId().toString()).toList();
        keyUnkeyedEntities(entityRules, ids);

        Set<EntityRef> entities = new LinkedHashSet<>(graph.entitiesOf(ids));
        store.liveEntityKeysListing(ids).stream().map(EntityRef::parse).forEach(entities::add);

        EpisodeBuilder builder = new EpisodeBuilder(new IndependentSources(entityRules.sameFinding()));
        Map<EntityRef, List<CorroborationSignal>> signals = graph.eligibleSignals(entities, now);
        List<CorroboratedSignalEvent> events = new ArrayList<>();
        for (EntityRef entity : entities) {
            List<CorroborationSignal> entitySignals = signals.getOrDefault(entity, List.of());
            if (entitySignals.size() > degreeCap) {
                continue;
            }
            events.addAll(reconcile(entityRules, builder, entity, entitySignals, now));
        }
        return new CorroborationScanner.ScanResult(events, pending);
    }

    private void keyUnkeyedEntities(EntityRules entityRules, List<String> ids) {
        List<CorroborationGraph.KeyedEntity> keyed = graph.unkeyedEntitiesOf(ids).stream()
                .map(n -> new CorroborationGraph.KeyedEntity(n.label(), n.name(),
                        entityRules.canonicalKey(n.label(), n.name())))
                .toList();
        if (!keyed.isEmpty()) {
            graph.setKeys(keyed);
        }
    }

    private List<CorroboratedSignalEvent> reconcile(EntityRules entityRules, EpisodeBuilder builder,
                                                    EntityRef entity, List<CorroborationSignal> signals,
                                                    Instant now) {
        String entityKey = entity.entityKey();
        Optional<String> excludedReason = entityRules.excludedReason(entity.label(), entity.key());

        Map<String, List<Episode>> byScope = new LinkedHashMap<>();
        byScope.put("", builder.build(signals));
        if (excludedReason.isEmpty()) {
            Set<String> tickers = new TreeSet<>();
            signals.forEach(s -> tickers.addAll(s.tickers()));
            for (String ticker : tickers) {
                byScope.put(ticker, builder.build(signals.stream().filter(s -> s.tickers().contains(ticker)).toList()));
            }
        }

        Map<String, CorroborationRow> existing = new HashMap<>();
        for (CorroborationRow row : store.rows(entityKey)) {
            existing.put(rowKey(row.ticker(), row.participantsHash()), row);
        }

        List<CorroboratedSignalEvent> events = new ArrayList<>();
        Set<String> produced = new HashSet<>();
        for (Map.Entry<String, List<Episode>> scope : byScope.entrySet()) {
            String ticker = scope.getKey();
            String reason = ticker.isEmpty() ? excludedReason.orElse(null) : null;
            for (Episode episode : scope.getValue()) {
                String hash = episode.participantsHash();
                produced.add(rowKey(ticker, hash));
                CorroborationRow row = existing.get(rowKey(ticker, hash));
                if (row == null) {
                    row = new CorroborationRow(entityKey, ticker, hash, uuids(episode),
                            builder.distinctSourceCount(episode), episode.corroboratedAt(), episode.openedAt(),
                            now, reason, null, null);
                    store.insert(row);
                } else {
                    if (!row.live()) {
                        store.revive(entityKey, ticker, hash);
                    }
                    if (!Objects.equals(row.excludedReason(), reason)) {
                        store.setExcludedReason(entityKey, ticker, hash, reason);
                    }
                }
                if (reason == null && row.publishedAt() == null) {
                    store.markPublished(entityKey, ticker, hash, now);
                    events.add(new CorroboratedSignalEvent(entityKey, ticker, hash, uuids(episode),
                            builder.distinctSourceCount(episode), episode.sourceTypes(), episode.corroboratedAt(),
                            episode.openedAt(), row.firstDetectedAt(), CorroboratedSignalEvent.SCHEMA_VERSION));
                }
            }
        }

        for (CorroborationRow row : existing.values()) {
            if (row.live() && !produced.contains(rowKey(row.ticker(), row.participantsHash()))) {
                store.supersede(entityKey, row.ticker(), row.participantsHash(),
                        successor(row, byScope.getOrDefault(row.ticker(), List.of())));
            }
        }
        return events;
    }

    private static String successor(CorroborationRow row, List<Episode> scopeEpisodes) {
        Set<String> participants = new HashSet<>();
        row.participantEventIds().forEach(id -> participants.add(id.toString()));
        for (Episode episode : scopeEpisodes) {
            if (episode.participants().stream().anyMatch(p -> participants.contains(p.eventId()))) {
                return episode.participantsHash();
            }
        }
        return SUPERSEDED_BY_RULES;
    }

    private static List<UUID> uuids(Episode episode) {
        return episode.sortedEventIds().stream().map(UUID::fromString).toList();
    }

    private static String rowKey(String ticker, String hash) {
        return ticker + "\u0000" + hash;
    }
}
