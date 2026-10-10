package dev.auspex.corehub.kafka;

import org.neo4j.driver.Driver;
import org.springframework.stereotype.Component;

@Component
public class Neo4jStoreProbe implements StoreProbe {

    private final Driver driver;

    public Neo4jStoreProbe(Driver driver) {
        this.driver = driver;
    }

    @Override
    public String name() {
        return "neo4j";
    }

    @Override
    public boolean isUp() {
        driver.verifyConnectivity();
        return true;
    }
}
