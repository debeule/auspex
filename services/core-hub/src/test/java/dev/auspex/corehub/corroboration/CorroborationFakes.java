package dev.auspex.corehub.corroboration;

import java.time.Instant;
import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;

/** In-memory graph and store for unit tests of the scan and the rules sync. */
final class CorroborationFakes {

    private CorroborationFakes() {}

    static String id(int n) {
        return new UUID(0L, n).toString();
    }

    /** Signals with their entity names (label to names) and tickers; nodes keyed as the real graph keys them. */
    static final class Graph implements CorroborationGraph {
        record Node(String label, String name) {}

        final Map<String, CorroborationSignal> signals = new LinkedHashMap<>();
        final Map<String, Set<Node>> links = new LinkedHashMap<>();
        final Map<Node, String> keys = new LinkedHashMap<>();
        final Map<String, String> tokens = new LinkedHashMap<>();
        final Set<String> pending = new LinkedHashSet<>();
        final List<String> calls = new ArrayList<>();

        void add(int n, String sourceType, String date, String label, String entity, String... tickers) {
            String id = id(n);
            signals.put(id, new CorroborationSignal(id, sourceType, Instant.parse(date + "T00:00:00Z"), null,
                    Set.of(tickers)));
            Node node = new Node(label, entity);
            links.computeIfAbsent(id, k -> new LinkedHashSet<>()).add(node);
            keys.putIfAbsent(node, null);
            tokens.put(id, UUID.randomUUID().toString());
            pending.add(id);
        }

        @Override
        public List<CorroborationScanner.PendingSignal> readPending(Instant now, int limit) {
            calls.add("readPending " + now);
            return pending.stream()
                    .filter(id -> !signals.get(id).publishedDate().isAfter(now))
                    .limit(limit)
                    .map(id -> new CorroborationScanner.PendingSignal(UUID.fromString(id), tokens.get(id)))
                    .toList();
        }

        @Override
        public List<EntityNode> unkeyedEntitiesOf(List<String> eventIds) {
            return eventIds.stream().flatMap(id -> links.getOrDefault(id, Set.of()).stream())
                    .filter(n -> keys.get(n) == null).distinct()
                    .map(n -> new EntityNode(n.label(), n.name())).toList();
        }

        @Override
        public List<EntityNode> allEntities() {
            calls.add("allEntities");
            return keys.keySet().stream().map(n -> new EntityNode(n.label(), n.name())).toList();
        }

        @Override
        public void setKeys(List<KeyedEntity> keyed) {
            calls.add("setKeys " + keyed.size());
            keyed.forEach(k -> keys.put(new Node(k.label(), k.name()), k.key()));
        }

        @Override
        public Set<EntityRef> entitiesOf(List<String> eventIds) {
            Set<EntityRef> out = new LinkedHashSet<>();
            for (String id : eventIds) {
                for (Node n : links.getOrDefault(id, Set.of())) {
                    if (keys.get(n) != null) {
                        out.add(new EntityRef(n.label(), keys.get(n)));
                    }
                }
            }
            return out;
        }

        @Override
        public Map<EntityRef, List<CorroborationSignal>> eligibleSignals(Collection<EntityRef> entities, Instant now) {
            calls.add("eligibleSignals " + now);
            Map<EntityRef, List<CorroborationSignal>> out = new LinkedHashMap<>();
            for (EntityRef entity : entities) {
                for (Map.Entry<String, Set<Node>> link : links.entrySet()) {
                    CorroborationSignal s = signals.get(link.getKey());
                    boolean onEntity = link.getValue().stream().anyMatch(n -> n.label().equals(entity.label())
                            && Objects.equals(keys.get(n), entity.key()));
                    if (onEntity && !s.publishedDate().isAfter(now)) {
                        out.computeIfAbsent(entity, e -> new ArrayList<>()).add(s);
                    }
                }
            }
            return out;
        }

        @Override
        public List<String> allSignalIds() {
            calls.add("allSignalIds");
            return List.copyOf(signals.keySet());
        }

        @Override
        public void markPending(List<String> eventIds) {
            calls.add("markPending " + eventIds.size());
            eventIds.forEach(id -> {
                pending.add(id);
                tokens.put(id, UUID.randomUUID().toString());
            });
        }

        @Override
        public void clearPending(List<CorroborationScanner.PendingSignal> handled) {
            for (CorroborationScanner.PendingSignal p : handled) {
                if (p.writeToken().equals(tokens.get(p.eventId().toString()))) {
                    pending.remove(p.eventId().toString());
                }
            }
        }
    }

    static final class Store implements CorroborationStore {
        String appliedHash;
        final List<CorroborationRow> rows = new ArrayList<>();
        final List<String> calls;

        Store() {
            this(new ArrayList<>());
        }

        /** A store recording its calls into {@code calls}, which a graph may share to show order. */
        Store(List<String> calls) {
            this.calls = calls;
        }

        @Override
        public String appliedRulesHash() {
            return appliedHash;
        }

        @Override
        public void storeAppliedRulesHash(String hash, Instant appliedAt) {
            calls.add("storeAppliedRulesHash");
            appliedHash = hash;
        }

        @Override
        public Set<String> liveEntityKeysListing(List<String> eventIds) {
            Set<String> out = new LinkedHashSet<>();
            for (CorroborationRow r : rows) {
                if (r.live() && r.participantEventIds().stream().anyMatch(u -> eventIds.contains(u.toString()))) {
                    out.add(r.entityKey());
                }
            }
            return out;
        }

        @Override
        public List<CorroborationRow> rows(String entityKey) {
            return rows.stream().filter(r -> r.entityKey().equals(entityKey)).toList();
        }

        @Override
        public void insert(CorroborationRow row) {
            if (find(row.entityKey(), row.ticker(), row.participantsHash()) < 0) {
                rows.add(row);
            }
        }

        @Override
        public void revive(String entityKey, String ticker, String hash) {
            update(entityKey, ticker, hash, r -> with(r, r.excludedReason(), r.publishedAt(), null));
        }

        @Override
        public void supersede(String entityKey, String ticker, String hash, String by) {
            update(entityKey, ticker, hash, r -> with(r, r.excludedReason(), r.publishedAt(), by));
        }

        @Override
        public void setExcludedReason(String entityKey, String ticker, String hash, String reason) {
            update(entityKey, ticker, hash, r -> with(r, reason, r.publishedAt(), r.supersededBy()));
        }

        @Override
        public void markPublished(String entityKey, String ticker, String hash, Instant at) {
            update(entityKey, ticker, hash, r -> with(r, r.excludedReason(), at, r.supersededBy()));
        }

        List<CorroborationRow> live() {
            return rows.stream().filter(CorroborationRow::live).toList();
        }

        private int find(String entityKey, String ticker, String hash) {
            for (int i = 0; i < rows.size(); i++) {
                CorroborationRow r = rows.get(i);
                if (r.entityKey().equals(entityKey) && r.ticker().equals(ticker) && r.participantsHash().equals(hash)) {
                    return i;
                }
            }
            return -1;
        }

        private void update(String entityKey, String ticker, String hash,
                            java.util.function.UnaryOperator<CorroborationRow> change) {
            int i = find(entityKey, ticker, hash);
            rows.set(i, change.apply(rows.get(i)));
        }

        private static CorroborationRow with(CorroborationRow r, String reason, Instant published, String supersededBy) {
            return new CorroborationRow(r.entityKey(), r.ticker(), r.participantsHash(), r.participantEventIds(),
                    r.distinctSourceCount(), r.corroboratedAt(), r.episodeOpenedAt(), r.firstDetectedAt(), reason,
                    published, supersededBy);
        }
    }
}
