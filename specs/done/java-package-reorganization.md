# Java Package Reorganization

**Status:** done
**Blocked by:** —
**Branch:** `feature/java-package-reorganization`

---

## Context

`core-hub` is organized by layer: `config/`, `kafka/`, `model/`, `rest/`, `service/`. The `service/` package holds 10 classes spanning three unrelated domains — signal ingestion, corroboration, and raw audit. The `model/` package has exactly two classes. `SignalQueryService` lives in `rest/` despite having no HTTP concerns — it queries Neo4j and Postgres directly and is only placed there because the REST controller happens to call it.

The package structure makes the system hard to navigate because it tells you how code is wired, not what it does. This spec reorganizes packages to reflect domain boundaries without changing any class internals or behavior.

## What this builds

All classes are moved to feature packages. No class body changes. No behavior changes. The full test suite passes before and after.

### New package structure

```
dev.auspex.corehub
  audit/
    RawAuditService
  config/
    JacksonConfig, KafkaConfig, Neo4jSchemaInitializer,
    PersistenceConfig, SchedulingConfig, WebConfig          (unchanged)
  corroboration/
    CorroborationService (interface)
    CorroborationScorer
    CorroboratedSignalEvent
    EntityNormalizer (interface)
    IdentityEntityNormalizer
    ScheduledCorroborationService
  kafka/
    RawListener, SignalListener, UnknownMajorVersionException  (unchanged)
  persistence/
    Neo4jWriteService
    PostgresWriteService
  query/
    SignalQueryService
  rest/
    GlobalExceptionHandler, SignalController, TickerValidationException
    dto/  (unchanged)
  signal/
    GraphUpdateService
    ResearchSignalEvent
    SchemaVersion
```

The `model/` and `service/` packages are deleted entirely — their contents scatter to the packages above.

### Package rationale

| Package | Why |
|---|---|
| `signal/` | Domain model + application service for signal ingestion. `GraphUpdateService` coordinates the two-store write — it is an application service, not infrastructure. |
| `persistence/` | Infrastructure adapters that write to Neo4j and Postgres. Depend on domain models; nothing depends on them except `signal/`. |
| `corroboration/` | Everything that belongs to the corroboration domain: interface, scorer, result record, entity normalizer, implementation. |
| `audit/` | Standalone raw-ingestion audit — no relationship to the corroboration or signal domain. |
| `query/` | Read-side service. `SignalQueryService` is a domain service that queries both stores; placing it in `rest/` was wrong. |
| `rest/` | HTTP driving adapters only. No direct database access. |

### ArchUnit rule update

The existing `test_no_query_built_by_string_concatenation` rule targets `dev.auspex.corehub.service..`. After this spec, `service/` does not exist. Update the rule to cover the new service-layer packages:

```java
methods()
    .that().areDeclaredInClassesThat().resideInAnyPackage(
        "dev.auspex.corehub.signal..",
        "dev.auspex.corehub.corroboration..",
        "dev.auspex.corehub.audit..",
        "dev.auspex.corehub.query.."
    )
    .should(/* existing condition unchanged */)
```

### Import updates required

Every class that imported from `dev.auspex.corehub.model.*` or `dev.auspex.corehub.service.*` needs its import updated. Integration test classes are in the flat `dev.auspex.corehub` package and import service-layer classes directly — update those imports too. Class bodies are otherwise unchanged.

## Out of scope

- Any logic changes inside class bodies
- Renaming classes (that is in the service-decomposition spec)
- Introducing new interfaces or splitting any class
- Changing Spring configuration, `@Transactional` qualifiers, or bean names
- Moving or renaming test files — test files update their imports but stay in `dev.auspex.corehub`

## Constraints

- `@SpringBootApplication` on `CoreHubApplication` scans `dev.auspex.corehub` and all sub-packages. Moving classes to sub-packages does not break component scanning — verify this is still true after the move.
- `CoreHubApplication` has `@EnableJpaRepositories(basePackages = "dev.auspex.corehub.repository")` and `@EnableNeo4jRepositories(basePackages = "dev.auspex.corehub.graph")`. Those packages do not exist yet and this spec does not create them — the annotations are forward declarations for future JPA/SDN repository specs. Leave them untouched.
- Every `@Transactional` in the codebase must keep its `transactionManager=` qualifier — the ArchUnit rule enforces this. Do not accidentally strip qualifiers when updating imports.
- The no-string-query ArchUnit rule must be updated to cover the new packages before the test suite is run, or it will silently pass by checking an empty package.
- Invariants 1 and 2 (sole-writer boundaries) are structural. The persistence/ package must not be imported from kafka/, rest/, or config/. The new ArchUnit rules (see Required tests) enforce this.

## Required tests

The primary assertion is behavioral: all existing tests pass with only import path changes.

**New ArchUnit rules in `ArchRulesTest.java`:**

- `test_kafka_package_does_not_import_rest_package` — classes in `dev.auspex.corehub.kafka..` do not depend on `dev.auspex.corehub.rest..`.
- `test_persistence_package_only_imported_from_signal_and_corroboration` — classes in `dev.auspex.corehub.persistence..` are only accessed from `dev.auspex.corehub.signal..` and `dev.auspex.corehub.corroboration..`. No direct persistence access from `kafka..`, `rest..`, `query..`, or `audit..`.
- `test_rest_package_has_no_direct_database_imports` — classes in `dev.auspex.corehub.rest..` do not import `org.springframework.jdbc..*`, `org.neo4j.driver..*`. The `SignalQueryService` has moved out of `rest/` so this rule simply confirms the boundary.
- `test_no_query_built_by_string_concatenation_in_service_packages` — updated version of the existing rule, covering all four service-layer packages listed above instead of the deleted `service..`.

## Definition of done

```bash
cd services/core-hub && ./gradlew check
```

All tests pass. The build must not complete with `UP-TO-DATE` on the test task — use `--rerun-tasks` to confirm tests ran. Check reported test count matches pre-refactor count.

```bash
cd services/core-hub && ./gradlew test --rerun-tasks 2>&1 | grep -E "tests|PASS|FAIL"
cd services/core-hub && ./gradlew integrationTest --rerun-tasks 2>&1 | grep -E "tests|PASS|FAIL"
```

No test count regression. The four new ArchUnit rules appear as passing test cases in the unit suite output.

## Notes

- Git moves should be tracked with `git mv` so blame history is preserved. Example: `git mv src/main/java/dev/auspex/corehub/service/GraphUpdateService.java src/main/java/dev/auspex/corehub/signal/GraphUpdateService.java`. Update the `package` declaration inside the file after the move.
- IDEs can do this rename automatically (IntelliJ: Refactor → Move) and will update all imports in one step. If doing it manually, update the `package` declaration first, then update all import references — this order avoids "unresolved symbol" cascades.
- The integration tests live in the flat `dev.auspex.corehub` package and import service classes. They will need import updates but no logic changes.
- This spec does not rename `GraphUpdateService` — that happens in the service-decomposition spec. The class moves to `signal/` with its current name.