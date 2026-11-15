package dev.auspex.corehub;

import dev.auspex.corehub.corroboration.CorroborationRulesSync;
import dev.auspex.corehub.corroboration.CorroborationService;
import dev.auspex.corehub.corroboration.EntityRules;
import dev.auspex.corehub.persistence.Neo4jWriteService;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.neo4j.driver.Session;
import org.springframework.beans.factory.annotation.Autowired;

import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

class CorroborationRulesSyncIT extends AbstractIT {

    private static final Set<String> SOURCE_TYPES =
            Set.of("mock", "biorxiv", "clinicaltrials", "pubmed", "edgar", "epo_ops");

    @Autowired
    Neo4jWriteService graph;

    @Autowired
    CorroborationService corroborationService;

    @Autowired
    CorroborationRulesSync rulesSync;

    @Autowired
    EntityRules fileRules;

    CorroborationSignals signals;

    @BeforeEach
    void setUpSignals() {
        signals = new CorroborationSignals(objectMapper, jdbcTemplate, neo4jDriver);
    }

    @AfterEach
    void restoreFileRules() {
        rulesSync.sync(fileRules);
    }

    private static EntityRules rules(String synonyms, String excluded) {
        String yaml = """
                synonyms:
                  Mechanism:
                    gene editing: [genome editing]
                %s
                excluded:
                  Mechanism:
                    - gene therapy
                %s
                same_finding:
                  source_type_pairs: [[biorxiv, pubmed]]
                  title_token_jaccard_min: 0.8
                """.formatted(synonyms, excluded);
        return EntityRules.load(yaml.getBytes(StandardCharsets.UTF_8), SOURCE_TYPES);
    }

    private UUID write(String sourceType, String date, List<String> genes, List<String> mechanisms,
                       List<String> companies) {
        UUID id = UUID.randomUUID();
        graph.upsert(signals.event(id, sourceType, date, sourceType + " " + date, genes, mechanisms, companies));
        return id;
    }

    private String key(String label, String name) {
        try (Session session = neo4jDriver.session()) {
            return session.run("MATCH (e {name: $name}) WHERE $label IN labels(e) RETURN e.corroboration_key AS k",
                    Map.of("name", name, "label", label)).single().get("k").asString();
        }
    }

    @Test
    void syncWithChangedRulesRekeysEntitiesAndRebuildsRecords() {
        UUID a = write("biorxiv", "2024-01-01", List.of(), List.of("Base Editing"), List.of());
        UUID b = write("edgar", "2024-01-10", List.of(), List.of("base-editor"), List.of());
        corroborationService.runCorroboration();
        assertThat(signals.all()).isEmpty();
        assertThat(key("Mechanism", "base-editor")).isEqualTo("base editor");

        EntityRules changed = rules("    base editing: [base editor]", "");
        rulesSync.sync(changed);

        assertThat(key("Mechanism", "base-editor")).isEqualTo("base editing");
        assertThat(jdbcTemplate.queryForObject("SELECT rules_hash FROM corroboration_rules_state", String.class))
                .isEqualTo(changed.hash());
        assertThat(signals.isPending(a)).isTrue();
        assertThat(signals.isPending(b)).isTrue();

        corroborationService.runCorroboration();

        assertThat(signals.live()).singleElement().satisfies(row -> {
            assertThat(row.entityKey()).isEqualTo("base editing:Mechanism");
            assertThat(row.participants()).containsExactlyInAnyOrder(a, b);
        });
        assertThat(signals.isPending(a)).isFalse();
    }

    @Test
    void entityNewlyExcludedKeepsItsRecordExcludedAndSupersedesItsTickerRecords() {
        write("biorxiv", "2024-01-01", List.of(), List.of("exon skipping"), List.of("Acme Bio"));
        write("edgar", "2024-01-10", List.of(), List.of("exon skipping"), List.of("Acme Bio"));
        signals.setTicker("Acme Bio", "ACME");
        corroborationService.runCorroboration();
        assertThat(signals.live()).extracting(CorroborationSignals.Row::ticker).containsExactlyInAnyOrder("", "ACME");

        rulesSync.sync(rules("", "    - exon skipping"));
        corroborationService.runCorroboration();

        assertThat(signals.live()).singleElement().satisfies(row -> {
            assertThat(row.ticker()).isEmpty();
            assertThat(row.entityKey()).isEqualTo("exon skipping:Mechanism");
            assertThat(row.excludedReason()).isEqualTo("broad_entity");
            assertThat(row.publishedAt()).isNotNull();
        });
        assertThat(jdbcTemplate.queryForObject(
                "SELECT superseded_by FROM corroboration WHERE ticker = 'ACME'", String.class)).isEqualTo("rules");
    }
}
