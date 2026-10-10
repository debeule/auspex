package dev.auspex.corehub.arch;

import com.tngtech.archunit.core.domain.JavaClass;
import com.tngtech.archunit.core.domain.JavaClasses;
import com.tngtech.archunit.core.domain.JavaMethod;
import com.tngtech.archunit.core.importer.ClassFileImporter;
import com.tngtech.archunit.lang.ArchCondition;
import com.tngtech.archunit.lang.ConditionEvents;
import com.tngtech.archunit.lang.SimpleConditionEvent;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.transaction.annotation.Transactional;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.Set;
import java.util.TreeSet;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.methods;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;
import static org.assertj.core.api.Assertions.assertThat;

class ArchRulesTest {

    private static JavaClasses importedClasses;

    @BeforeAll
    static void importClasses() {
        importedClasses = new ClassFileImporter()
                .importPackages("dev.auspex.corehub");
    }

    @Test
    void test_no_unqualified_transactional() {
        methods()
                .that().areAnnotatedWith(Transactional.class)
                .and().areDeclaredInClassesThat().resideInAPackage("dev.auspex.corehub..")
                .should(new ArchCondition<JavaMethod>("have a non-empty transactionManager attribute") {
                    @Override
                    public void check(JavaMethod method, ConditionEvents events) {
                        Transactional annotation = method.getAnnotationOfType(Transactional.class);
                        if (annotation.transactionManager().isEmpty()) {
                            events.add(SimpleConditionEvent.violated(method,
                                    "Unqualified @Transactional on " + method.getFullName()
                                    + " — must specify transactionManager="));
                        }
                    }
                })
                .check(importedClasses);
    }

    @Test
    void test_no_query_built_by_string_concatenation_in_service_packages() {
        methods()
                .that().areDeclaredInClassesThat().resideInAnyPackage(
                        "dev.auspex.corehub.signal..",
                        "dev.auspex.corehub.corroboration..",
                        "dev.auspex.corehub.audit..",
                        "dev.auspex.corehub.query..",
                        "dev.auspex.corehub.health.."
                )
                .should(new ArchCondition<JavaMethod>("not call java.sql.Statement raw-string methods") {
                    @Override
                    public void check(JavaMethod method, ConditionEvents events) {
                        method.getCallsFromSelf().stream()
                                .filter(call -> {
                                    String owner = call.getTarget().getOwner().getFullName();
                                    String name  = call.getTarget().getName();
                                    return (owner.equals("java.sql.Statement")
                                            || owner.equals("java.sql.Connection"))
                                            && (name.equals("execute")
                                                || name.equals("executeQuery")
                                                || name.equals("executeUpdate")
                                                || name.equals("createStatement"));
                                })
                                .forEach(call -> events.add(SimpleConditionEvent.violated(method,
                                        "Raw Statement call at " + call.getSourceCodeLocation()
                                        + " — use PreparedStatement via JdbcTemplate instead")));
                    }
                })
                .allowEmptyShould(true)
                .check(importedClasses);
    }

    @Test
    void test_kafka_package_does_not_import_rest_package() {
        noClasses()
                .that().resideInAPackage("dev.auspex.corehub.kafka..")
                .should().dependOnClassesThat().resideInAPackage("dev.auspex.corehub.rest..")
                .check(importedClasses);
    }

    @Test
    void test_persistence_package_only_imported_from_signal_and_corroboration() {
        noClasses()
                .that().resideOutsideOfPackages(
                        "dev.auspex.corehub.signal..",
                        "dev.auspex.corehub.corroboration..",
                        "dev.auspex.corehub.persistence.."
                )
                .should().dependOnClassesThat().resideInAPackage("dev.auspex.corehub.persistence..")
                .check(importedClasses);
    }

    @Test
    void test_rest_package_has_no_direct_database_imports() {
        noClasses()
                .that().resideInAPackage("dev.auspex.corehub.rest..")
                .should().dependOnClassesThat()
                .resideInAnyPackage("org.springframework.jdbc..", "org.neo4j.driver..")
                .check(importedClasses);
    }

    /**
     * Relationship types are taken from the Cypher text blocks in each persistence class's constant
     * pool, so a writer cannot drift from the graph model in requirements §9.
     */
    @Test
    void noRelationshipTypeOtherThanThoseInTheGraphModelIsWritten() throws Exception {
        Pattern relationship = Pattern.compile("\\[\\s*\\w*\\s*:\\s*([A-Z_]+(?:\\s*\\|\\s*[A-Z_]+)*)");
        Set<String> written = new TreeSet<>();
        for (JavaClass javaClass : importedClasses) {
            if (!javaClass.getPackageName().startsWith("dev.auspex.corehub.persistence")) continue;
            String constants;
            try (InputStream in = javaClass.getSource().orElseThrow().getUri().toURL().openStream()) {
                constants = new String(in.readAllBytes(), StandardCharsets.ISO_8859_1);
            }
            Matcher m = relationship.matcher(constants);
            while (m.find()) {
                for (String type : m.group(1).split("\\|")) written.add(type.trim());
            }
        }

        assertThat(written).isNotEmpty();
        assertThat(written).isSubsetOf("TARGETS", "USES_MECHANISM", "MENTIONS");
    }
}
