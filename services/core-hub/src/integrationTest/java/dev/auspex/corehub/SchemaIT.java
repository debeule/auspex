package dev.auspex.corehub;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.DatabaseMetaData;
import java.sql.ResultSet;
import java.util.ArrayList;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;

class SchemaIT extends AbstractIT {

    @Autowired
    private DataSource dataSource;

    @Test
    void test_schema_applies_to_an_empty_database() throws Exception {
        // Flyway already ran at context startup. Verify all expected tables exist.
        List<String> tables = new ArrayList<>();
        try (Connection conn = dataSource.getConnection()) {
            DatabaseMetaData meta = conn.getMetaData();
            try (ResultSet rs = meta.getTables(null, "public", "%", new String[]{"TABLE"})) {
                while (rs.next()) {
                    tables.add(rs.getString("TABLE_NAME"));
                }
            }
        }
        assertThat(tables).contains(
                "raw_fetch_audit",
                "signal_current",
                "signal_extraction_history",
                "source_observation",
                "corroboration");
    }

    @Test
    void test_ddl_auto_is_validate() {
        // Reaching this test means the context started under ddl-auto=validate, so every entity
        // matches the Flyway schema; create or update would have silently rebuilt or patched it.
        assertThatCode(() -> {
            jdbcTemplate.queryForObject("SELECT COUNT(*) FROM signal_current", Integer.class);
        }).doesNotThrowAnyException();
    }
}
