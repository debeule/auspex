package dev.auspex.corehub;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.data.jpa.repository.config.EnableJpaRepositories;
import org.springframework.data.neo4j.repository.config.EnableNeo4jRepositories;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * JPA and Neo4j repositories are in separate base packages so that
 * Spring Data can wire each to its own transaction manager without ambiguity.
 * Every @Transactional in application code must be qualified — ArchUnit enforces this.
 */
@SpringBootApplication
@EnableJpaRepositories(
        basePackages = "dev.auspex.corehub.repository",
        transactionManagerRef = "jpaTransactionManager"
)
@EnableNeo4jRepositories(
        basePackages = "dev.auspex.corehub.graph",
        transactionManagerRef = "neo4jTransactionManager"
)
@EnableScheduling
public class CoreHubApplication {
    public static void main(String[] args) {
        SpringApplication.run(CoreHubApplication.class, args);
    }
}
