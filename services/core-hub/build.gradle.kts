import org.gradle.api.tasks.testing.logging.TestExceptionFormat

plugins {
    java
    id("org.springframework.boot") version "4.1.0"
    id("jvm-test-suite")
}

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(25)
    }
}

repositories {
    mavenCentral()
}

// The Spring Boot plugin does not auto-apply the BOM in Gradle 9.7 without the
// dependency-management plugin. Use Gradle-native platform() instead — no plugin needed.
// The platform must be declared in both scopes for version constraints to propagate.
dependencies {
    implementation(platform("org.springframework.boot:spring-boot-dependencies:4.1.0"))
    testImplementation(platform("org.springframework.boot:spring-boot-dependencies:4.1.0"))

    implementation("org.springframework.boot:spring-boot-starter-data-jpa")
    implementation("org.springframework.boot:spring-boot-starter-data-neo4j")
    implementation("org.springframework.kafka:spring-kafka")
    implementation("org.springframework.boot:spring-boot-kafka")
    implementation("org.flywaydb:flyway-core")
    implementation("org.flywaydb:flyway-database-postgresql")
    implementation("org.springframework.boot:spring-boot-flyway")
    implementation("org.postgresql:postgresql")
    implementation("org.springframework.boot:spring-boot-starter-validation")
    implementation("com.fasterxml.jackson.core:jackson-databind")
    implementation("com.fasterxml.jackson.datatype:jackson-datatype-jsr310")
}

// ── Test suites ───────────────────────────────────────────────────────────────

testing {
    suites {
        named<JvmTestSuite>("test") {
            useJUnitJupiter()
            dependencies {
                implementation("org.springframework.boot:spring-boot-starter-test")
                implementation(libs.archunit.junit5)
            }
        }

        register<JvmTestSuite>("integrationTest") {
            useJUnitJupiter()
            dependencies {
                implementation(platform("org.springframework.boot:spring-boot-dependencies:4.1.0"))
                implementation(project())
                implementation("org.springframework.boot:spring-boot-starter-test")
                implementation("org.springframework.boot:spring-boot-testcontainers")
                implementation("org.springframework.kafka:spring-kafka-test")
                implementation(libs.testcontainers.core)
                implementation(libs.testcontainers.kafka)
                implementation(libs.testcontainers.postgresql)
                implementation(libs.testcontainers.neo4j)
            }
        }
    }
}

// Expose main implementation dependencies to the integration test compile and runtime classpaths.
configurations.named("integrationTestImplementation") {
    extendsFrom(configurations["implementation"])
}
configurations.named("integrationTestRuntimeOnly") {
    extendsFrom(configurations["runtimeOnly"])
}

tasks.named("check") {
    dependsOn(testing.suites.named("integrationTest"))
}

// ── timezoneCheck — forked JVM under America/New_York, @Tag("timezoneCheck") ──

tasks.register<Test>("timezoneCheck") {
    group = "verification"
    description = "Runs timezone-sensitive integration tests under America/New_York"
    useJUnitPlatform {
        includeTags("timezoneCheck")
    }
    jvmArgs("-Duser.timezone=America/New_York")
    testClassesDirs = sourceSets["integrationTest"].output.classesDirs
    classpath = sourceSets["integrationTest"].runtimeClasspath
    failOnNoDiscoveredTests = true
    dependsOn("integrationTestClasses")
}

// ── Shared test task configuration ────────────────────────────────────────────

tasks.withType<Test>().configureEach {
    failOnNoDiscoveredTests = true
    testLogging {
        events("passed", "failed", "skipped")
        exceptionFormat = TestExceptionFormat.FULL
    }
}
