package dev.auspex.corehub.corroboration;

import org.junit.jupiter.api.Test;
import org.neo4j.driver.Driver;
import org.springframework.jdbc.core.JdbcTemplate;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

class CorroborationScannerTest {

    private static final Instant NOW = Instant.parse("2024-06-15T12:00:00Z");

    private CorroborationScanner scannerWithGroups(
            JdbcTemplate jdbc,
            Instant watermark,
            List<CorroborationScanner.EntityGroup> groups
    ) {
        return new CorroborationScanner(mock(Driver.class), jdbc, mock(EntityNormalizer.class)) {
            @Override
            protected Instant readWatermark() { return watermark; }
            @Override
            protected List<EntityGroup> findGroups(Instant wm) { return groups; }
            @Override
            protected void writeWatermark(Instant ts) {}
        };
    }

    @Test
    void test_scan_returns_empty_when_watermark_is_ahead_of_all_signals() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        CorroborationScanner scanner = scannerWithGroups(jdbc, NOW.plusSeconds(3600), List.of());

        List<CorroboratedSignalEvent> result = scanner.scan();

        assertThat(result).isEmpty();
        verifyNoInteractions(jdbc);
    }

    @Test
    void test_scan_does_not_publish_group_with_single_source_type() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        CorroborationScanner.EntityGroup group = new CorroborationScanner.EntityGroup(
                UUID.randomUUID(),
                "biorxiv",
                NOW,
                NOW,
                "BCL11A",
                "GeneTarget",
                List.of(new CorroborationScanner.Partner(UUID.randomUUID(), "biorxiv", NOW))
        );
        CorroborationScanner scanner = new CorroborationScanner(mock(Driver.class), jdbc, s -> s) {
            @Override
            protected Instant readWatermark() { return Instant.EPOCH; }
            @Override
            protected List<EntityGroup> findGroups(Instant wm) { return List.of(group); }
            @Override
            protected void writeWatermark(Instant ts) {}
        };

        List<CorroboratedSignalEvent> result = scanner.scan();

        assertThat(result).isEmpty();
    }

    @Test
    void test_scan_returns_event_for_qualifying_group() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        when(jdbc.update(any(org.springframework.jdbc.core.PreparedStatementCreator.class))).thenReturn(1);

        UUID triggerId = UUID.randomUUID();
        UUID partnerId = UUID.randomUUID();
        CorroborationScanner.EntityGroup group = new CorroborationScanner.EntityGroup(
                triggerId,
                "biorxiv",
                NOW.minusSeconds(3600),
                NOW,
                "BCL11A",
                "GeneTarget",
                List.of(new CorroborationScanner.Partner(partnerId, "clinicaltrials", NOW.minusSeconds(7200)))
        );
        CorroborationScanner scanner = new CorroborationScanner(mock(Driver.class), jdbc, s -> s) {
            @Override
            protected Instant readWatermark() { return Instant.EPOCH; }
            @Override
            protected List<EntityGroup> findGroups(Instant wm) { return List.of(group); }
            @Override
            protected void writeWatermark(Instant ts) {}
        };

        List<CorroboratedSignalEvent> result = scanner.scan();

        assertThat(result).hasSize(1);
        CorroboratedSignalEvent event = result.getFirst();
        assertThat(event.entityKey()).isEqualTo("BCL11A:GeneTarget");
        assertThat(event.participantEventIds()).containsExactlyInAnyOrder(triggerId, partnerId);
        assertThat(event.distinctSourceCount()).isEqualTo(2);
    }
}
