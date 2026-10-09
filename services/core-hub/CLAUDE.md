# CLAUDE.md — services/core-hub

Auto-loaded when working in this directory, in addition to the root CLAUDE.md.

## Commands
```bash
./gradlew test                              # unit only — inner loop
./gradlew integrationTest                   # container-backed only
./gradlew check                             # everything
./gradlew test --tests '*SomeTest'          # one class
./gradlew timezoneCheck                     # forked JVM, non-UTC default TZ
./gradlew test --rerun-tasks                # defeat up-to-date caching
```

## Naming
Root package `dev.auspex.corehub`. Topics `auspex.*`. Application database `auspex`, role `auspex_app`.

## Build layout
- **Kotlin DSL** (`build.gradle.kts`), Gradle wrapper committed, **Gradle 9.7.0**.
- Versions live in `gradle/libs.versions.toml` (version catalog) and must match `VERSIONS.md`. One source of truth per version, referenced from the catalog — never a literal version string in `build.gradle.kts`.
- Spring Boot Gradle plugin 4.1.0 applies the dependency BOM itself; **do not** add `io.spring.dependency-management`.
- Java toolchain pinned explicitly:
  ```kotlin
  java { toolchain { languageVersion = JavaLanguageVersion.of(25) } }
  ```
- Integration tests use the **JVM Test Suite** plugin: a separate `integrationTest` suite with its own source set at `src/integrationTest/java`, wired into `check`. This is the Gradle equivalent of Maven's Failsafe split — do not try to separate unit and container tests by filename inside one source set.
- `timezoneCheck` is its own `Test` task over a narrow subset, with `jvmArgs("-Duser.timezone=America/New_York")`.

## Rules specific to this service
- **Sole writer** to the application database and Neo4j. Nothing else may write.
- **Write order is Neo4j → Postgres → acknowledge.** `ack-mode: RECORD`. Never commit the offset before both stores return.
- **Every `@Transactional` must be qualified** — two transaction managers are on the classpath and an unqualified annotation silently binds to one of them. JPA and Neo4j repositories live in separate base packages.
- **Flyway owns the schema.** `ddl-auto: validate`. Never `update`.
- **`MERGE`, never `CREATE`**, for signal and entity nodes.
- **No string-built queries.** ArchUnit enforces it.
- **Java 25 records, no Lombok.** Constructor injection, no field injection.

## Testing
- `src/test/java/**/*Test.java` = unit, **no Spring context**. `src/integrationTest/java/**/*IT.java` = container-backed. Different source sets, different tasks.
- Containers are **static singletons started once per JVM** — not `@Testcontainers` per class. One Spring context, no `@DirtiesContext`, truncate between tests rather than restarting containers. Target: the container suite under 3 minutes.
- `CorroborationServiceContractTest` is **abstract**. Every `CorroborationService` implementation extends it unmodified. Do not inline its cases.
- Use `awaitility` for async assertions, never `Thread.sleep`.

## Traps
- **`./gradlew test` reports `UP-TO-DATE` and runs nothing when inputs are unchanged.** That is indistinguishable from a pass at a glance. Use `--rerun-tasks` when you need proof a test executed, and always read the test count.
- **Gradle 9 prefers the Configuration Cache.** If a build script does something it disallows, you get a configuration-time failure that reads nothing like a test failure. Fix the script; do not disable the cache to move on.
- **`ErrorHandlingDeserializer` is mandatory** — without it a malformed payload fails inside the poll loop, before the error handler, and the same offset retries forever.
- **DLT resolver:** Spring's default gives `.DLT` uppercase and the *same partition number*. We use lowercase `.dlt` and partition `-1`. **Re-verify against Spring Kafka 4.1** and record the result in `DECISIONS.md`.
- **`confidence_score`:** `BigDecimal` in the DTO (a primitive `double` would turn a missing field into a silent `0.0`), `NUMERIC(4,3)` in Postgres, `double` in Neo4j via an explicit converter (SDN may otherwise persist a string and break Cypher comparison).
- **`FAIL_ON_UNKNOWN_PROPERTIES=false`** on the consumer, or the first additive schema change dead-letters everything.
- **`MERGE (c:Company {ticker: null})` matches every null-ticker node.** MERGE on normalized `name`.
- **Boot 4.1 / Spring Framework 7 / Spring Kafka 4.1** is a major jump from the 3.x examples in most tutorials. When something contradicts a remembered 3.x behaviour, trust the 4.x docs.
