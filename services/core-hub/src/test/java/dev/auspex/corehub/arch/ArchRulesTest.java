package dev.auspex.corehub.arch;

import com.tngtech.archunit.core.domain.JavaClasses;
import com.tngtech.archunit.core.domain.JavaMethod;
import com.tngtech.archunit.core.importer.ClassFileImporter;
import com.tngtech.archunit.lang.ArchCondition;
import com.tngtech.archunit.lang.ConditionEvents;
import com.tngtech.archunit.lang.SimpleConditionEvent;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.transaction.annotation.Transactional;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.methods;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;

/**
 * ArchUnit rules for the application packages. No Spring context — runs in the unit suite.
 */
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
    void test_no_query_built_by_string_concatenation() {
        // Verifies that no service-layer method calls the raw Statement variants that accept
        // a plain String SQL argument. All JDBC must go through PreparedStatement
        // (via JdbcTemplate's parameterized overloads) and all Neo4j queries must use
        // the run(String, Map) form where parameters are separated from the query string.
        methods()
                .that().areDeclaredInClassesThat().resideInAPackage("dev.auspex.corehub.service..")
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
                .check(importedClasses);
    }
}
