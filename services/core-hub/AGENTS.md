# core-hub

## Owners

- `docs/core-hub/consumption.md`, `docs/core-hub/storage.md`, `docs/core-hub/corroboration.md`, `docs/core-hub/http-api.md`.
- Payloads, keys and dead letters: `docs/system/contracts.md`.

## Commands

Run from `services/core-hub/`. They need JDK 25 and Maven Central; cloud sessions have neither, so CI proves them there.

```bash
./gradlew test                          # unit only, inner loop
./gradlew integrationTest               # container-backed only (Docker; CI)
./gradlew check                         # everything
./gradlew test --tests '*SomeTest'      # one class
./gradlew timezoneCheck                 # forked JVM, non-UTC default time zone
./gradlew test --rerun-tasks            # defeat up-to-date caching
```

## Layout

- Root package `dev.auspex.corehub` under `src/main/java/`.
- `src/test/java/**/*Test.java`: unit tests, no Spring context (`test`).
- `src/integrationTest/java/**/*IT.java`: container-backed, own source set (`integrationTest`).
- `src/main/resources/db/migration/`: Flyway scripts.
- Dependency and plugin versions: `gradle/libs.versions.toml`.

## Requirements that bite here

- COR-001: extend `CorroborationServiceContractTest` unmodified.
- HUB-020: applied Flyway scripts are frozen, comments too.
- HUB-002: `ErrorHandlingDeserializer` on both listeners.
- CON-035: lowercase `.dlt` suffix.
- CON-036: dead-letter partition `-1`.
- CON-012: `confidence_score` as non-null `BigDecimal`.
- CON-029: unknown properties ignored.
- HUB-034: MERGE `Company` on name, not ticker.
- HUB-026: every `@Transactional` names its manager.
- HUB-014: offset committed after both stores return.
- INV-12: parameterised queries, ArchUnit.
- ENG-053: Kotlin DSL, versions only in the catalog.
- ENG-054: records, constructor injection, no Lombok.
- ENG-006: singleton containers, one Spring context.

## Trap pointers

- ENG-053: Gradle 9 configuration cache; Boot 4 and Spring Kafka 4 against 3.x examples: `docs/engineering/conventions.md`, Known traps.
- HUB-002: malformed payload without `ErrorHandlingDeserializer`: `docs/core-hub/consumption.md`, Known traps.
- CON-036: Spring's default `.DLT` and same partition: `docs/system/contracts.md`, Known traps.
- HUB-034: `MERGE` on a null ticker: `docs/core-hub/storage.md`, Known traps.
