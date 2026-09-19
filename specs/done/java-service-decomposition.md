# Java Service Decomposition

**Status:** done
**Blocked by:** [Java package reorganization](java-package-reorganization.md) — this spec renames and splits classes whose final package locations are established by the reorganization spec.
**Branch:** `feature/java-service-decomposition`

---

## Context

After the package reorganization, three structural problems remain that require class-body changes:

**1. `ScheduledCorroborationService` is a 265-line monolith.** It owns: the `@Scheduled` entry point, watermark read/write, a 90-line Cypher query that finds corroboration groups, group processing (hash computation, subset supersession, Postgres insert), and Kafka publishing. The domain logic — finding and recording corroborations — is inseparable from the scheduling infrastructure. The `CorroborationService` interface exists precisely so a future Kafka Streams implementation can substitute; but you cannot test the scanning logic in isolation, and you cannot substitute just the domain logic without also substituting the scheduler.

**2. `GraphUpdateService` name misleads.** The class writes to Neo4j AND Postgres. It is an application-layer use-case orchestrator, not a graph-specific concern. Its method `process()` is a domain operation name, not an infrastructure name.

**3. `SignalIngestionService` depends directly on concrete infrastructure classes.** After the rename, `SignalIngestionService` still has `Neo4jWriteService` and `PostgresWriteService` as constructor parameter types. The application service depends on infrastructure — the dependency points the wrong way for the hexagonal structure established by the package reorganization.

## What this builds

### 1. `CorroborationScanner` (new class in `corroboration/`)

Extracted from `ScheduledCorroborationService`. Contains all domain logic:

```java
@Service
class CorroborationScanner {

    // Constructor: Driver, JdbcTemplate, EntityNormalizer, @Value degreeCap

    /**
     * Reads the watermark, queries Neo4j for new corroboration groups, persists them,
     * advances the watermark, and returns the events that should be published.
     * Idempotent: ON CONFLICT DO NOTHING on the Postgres insert.
     */
    List<CorroboratedSignalEvent> scan() { ... }

    // Private: readWatermark, writeWatermark, findGroups, processGroup,
    //          supersedeSubsets, insertCorroboration, computeHash
    // Private records: EntityGroup, Partner
}
```

`scan()` returns `List<CorroboratedSignalEvent>` — the events that were newly persisted and should be published. An empty list means nothing new was found or everything was already recorded.

### 2. `ScheduledCorroborationService` (slimmed to ~40 lines)

Keeps the `@Scheduled` annotation and `CorroborationService` interface implementation. Delegates all domain logic to `CorroborationScanner`:

```java
@Service
class ScheduledCorroborationService implements CorroborationService {

    private final CorroborationScanner scanner;
    private final KafkaTemplate<Object, Object> corroboratedKafkaTemplate;

    @Scheduled(fixedDelayString = "${corroboration.interval-ms:30000}")
    @Override
    public void runCorroboration() {
        List<CorroboratedSignalEvent> events = scanner.scan();
        for (CorroboratedSignalEvent event : events) {
            corroboratedKafkaTemplate.send(CORROBORATED_TOPIC, event.entityKey(), event);
            log.info("corroboration published entity_key={} participants={} sources={}",
                    event.entityKey(), event.participantEventIds().size(), event.distinctSourceCount());
        }
    }
}
```

`CorroborationServiceContractTest` runs against `ScheduledCorroborationService` unmodified — the contract tests verify behavior, not implementation. The scanner is also independently testable.

### 3. `SignalIngestionService` (rename of `GraphUpdateService`)

Rename class and method:
- `GraphUpdateService` → `SignalIngestionService`
- `process(ResearchSignalEvent event)` → `ingest(ResearchSignalEvent event)`

Constructor parameter types change from concrete classes to interfaces (see §4 below).

`SignalListener` updates its dependency from `GraphUpdateService` to `SignalIngestionService` and calls `ingest()` instead of `process()`.

### 4. `SignalGraphPort` and `SignalRecordPort` interfaces (new, in `signal/`)

Two port interfaces that the application service depends on instead of the concrete write services:

```java
// signal/SignalGraphPort.java
public interface SignalGraphPort {
    void upsert(ResearchSignalEvent event);
}

// signal/SignalRecordPort.java
public interface SignalRecordPort {
    void upsert(ResearchSignalEvent event);
}
```

`Neo4jWriteService` and `PostgresWriteService` in `persistence/` implement these interfaces respectively. Their class bodies and SQL/Cypher are unchanged.

`SignalIngestionService` constructor:

```java
public SignalIngestionService(SignalGraphPort graphPort, SignalRecordPort recordPort) {
    this.graphPort = graphPort;
    this.recordPort = recordPort;
}
```

Spring autowires the concrete implementations because they are the only beans implementing the interfaces.

## Out of scope

- Changes to `CorroborationService` interface — it remains a single-method interface
- Changes to the Cypher query inside `CorroborationScanner` — extracted verbatim
- Changes to the Postgres SQL — extracted verbatim
- `RawAuditService` — not a decomposition target; it is already a single-responsibility class
- `SignalQueryService` — already clean; no changes needed
- JPA repository interfaces or SDN repositories — not introduced by this spec
- Any changes to the integration tests beyond updating import paths and the `GraphUpdateService` → `SignalIngestionService` reference

## Constraints

- **`CorroborationServiceContractTest` must pass unmodified.** It is an abstract class; `CorroborationServiceIT` extends it against the real `ScheduledCorroborationService`. The scanner extraction must not change any observable behavior.
- **Write order invariant preserved.** `SignalIngestionService.ingest()` still calls the graph port before the record port. The comment documenting this requirement moves to the new class.
- **`@Transactional` qualification preserved.** `PostgresWriteService.upsert()` keeps `@Transactional(transactionManager = "jpaTransactionManager")`. Neo4j writes use the driver's own transaction — no `@Transactional` annotation there. Do not add or remove qualifiers.
- **Invariant 2 holds.** `core-hub` is still the sole writer. The refactoring introduces no new writers.
- The ArchUnit `persistence.. only accessed from signal.. and corroboration..` rule (from the reorganization spec) continues to pass. `CorroborationScanner` is in `corroboration/` and may depend on `persistence/` indirectly via JdbcTemplate — but the ArchUnit rule checks package imports, not JdbcTemplate calls. Verify the rule still holds after this spec.

## Required tests

**Unit tests (no Spring context) in `SignalIngestionServiceTest.java`:**

- `test_ingest_calls_graph_port_before_record_port` — create a `SignalIngestionService` with mock `SignalGraphPort` and `SignalRecordPort`; call `ingest()`; verify `graphPort.upsert()` is called before `recordPort.upsert()` using Mockito `InOrder`.
- `test_ingest_calls_both_ports_with_same_event` — both port mocks receive the same `ResearchSignalEvent` instance.
- `test_ingest_propagates_graph_port_exception` — `graphPort.upsert()` throws `RuntimeException`; assert `recordPort.upsert()` is never called (offset not committed if Neo4j fails).

**Unit tests (no Spring context) in `CorroborationScannerTest.java`:**

- `test_scan_returns_empty_when_watermark_is_ahead_of_all_signals` — scanner backed by in-memory stubs; no groups returned from `findGroups`; `scan()` returns empty list and does not advance watermark past its current value.
- `test_scan_does_not_publish_group_with_single_source_type` — group with trigger and partner sharing the same `source_type`; `scan()` returns empty list.
- `test_scan_returns_event_for_qualifying_group` — group with trigger and partner from different source types within 90 days; `scan()` returns one event; event's `entityKey`, `participantEventIds`, and `distinctSourceCount` match expectations.

**Unit tests (no Spring context) in `ScheduledCorroborationServiceTest.java`:**

- `test_run_corroboration_publishes_each_event_returned_by_scanner` — mock scanner returns a list of two events; assert `KafkaTemplate.send()` called twice with the expected entity keys.
- `test_run_corroboration_does_not_call_kafka_when_scanner_returns_empty` — mock scanner returns empty list; assert `KafkaTemplate.send()` never called.

**Contract test (unchanged):**

- `CorroborationServiceContractTest` — abstract test class. `CorroborationServiceIT extends CorroborationServiceContractTest` must pass with no modifications to the abstract class.

## Definition of done

```bash
cd services/core-hub && ./gradlew test --tests '*SignalIngestionServiceTest' --tests '*CorroborationScannerTest' --tests '*ScheduledCorroborationServiceTest' --rerun-tasks
```

All new unit tests pass.

```bash
cd services/core-hub && ./gradlew integrationTest --rerun-tasks
```

All integration tests pass including `CorroborationServiceIT`. No test count regression.

```bash
cd services/core-hub && ./gradlew check --rerun-tasks
```

Full suite green including ArchUnit rules.

## Notes

- The inner records `EntityGroup` and `Partner` that are currently private to `ScheduledCorroborationService` move to `CorroborationScanner`. They can stay package-private.
- `CorroborationScanner` needs the `@Value("${corroboration.degree-cap:500}")` field that was on `ScheduledCorroborationService`. It moves with the logic.
- The `CORROBORATED_TOPIC` constant stays on `ScheduledCorroborationService` since that class is responsible for publishing. `CorroborationScanner` has no Kafka dependency.
- When writing the `CorroborationScannerTest`, the Neo4j query cannot run without a real driver. The unit test stubs at the scanner's method boundary (`findGroups` returns a pre-built list), not at the driver level. This avoids the need for a test container in the unit suite.
- The `test_ingest_calls_graph_port_before_record_port` test is the main regression guard against a future change accidentally reversing the write order. Write order matters: a Neo4j failure must prevent the Postgres write; a Postgres failure after Neo4j is acceptable (idempotent retry).
