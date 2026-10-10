package dev.auspex.corehub.kafka;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
public class PostgresStoreProbe implements StoreProbe {

    private final JdbcTemplate jdbcTemplate;

    public PostgresStoreProbe(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    @Override
    public String name() {
        return "postgres";
    }

    @Override
    public boolean isUp() {
        Integer one = jdbcTemplate.queryForObject("SELECT 1", Integer.class);
        return one != null && one == 1;
    }
}
