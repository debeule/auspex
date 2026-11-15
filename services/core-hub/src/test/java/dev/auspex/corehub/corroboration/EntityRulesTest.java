package dev.auspex.corehub.corroboration;

import com.fasterxml.jackson.databind.JsonNode;
import org.junit.jupiter.api.Test;
import org.yaml.snakeyaml.Yaml;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import java.util.stream.Collectors;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class EntityRulesTest {

    private static final Path COMMITTED = Path.of("../../config/corroboration/entity-rules.yaml");

    private static EntityRules rules(String yaml) {
        return EntityRules.load(yaml.getBytes(StandardCharsets.UTF_8), EpisodeCases.SOURCE_TYPES);
    }

    private static String file(String synonyms, String excluded, String pairs) {
        return """
                synonyms:
                %s
                excluded:
                %s
                same_finding:
                  source_type_pairs: %s
                  title_token_jaccard_min: 0.8
                """.formatted(synonyms, excluded, pairs);
    }

    private static final String NO_SYNONYMS = "  Mechanism: {}\n  GeneTarget: {}";
    private static final String NO_EXCLUDED = "  Mechanism: []\n  GeneTarget: []";
    private static final String PAIRS = "[[biorxiv, pubmed]]";

    @Test
    void geneTargetKeyIsUpperCasedWithSeparatorsRemoved() {
        EntityRules rules = rules(file(NO_SYNONYMS, NO_EXCLUDED, PAIRS));

        assertThat(rules.canonicalKey("GeneTarget", "IL-2")).isEqualTo("IL2");
        assertThat(rules.canonicalKey("GeneTarget", "il2")).isEqualTo("IL2");
        assertThat(rules.canonicalKey("GeneTarget", "IL 2")).isEqualTo("IL2");
    }

    @Test
    void mechanismKeyIsLowerCasedWithPunctuationAsOneSpace() {
        EntityRules rules = rules(file(NO_SYNONYMS, NO_EXCLUDED, PAIRS));

        assertThat(rules.canonicalKey("Mechanism", "CRISPR-Cas9")).isEqualTo("crispr cas9");
        assertThat(rules.canonicalKey("Mechanism", "CRISPR/Cas9")).isEqualTo("crispr cas9");
        assertThat(rules.canonicalKey("Mechanism", " Base -- Editing ")).isEqualTo("base editing");
    }

    @Test
    void synonymVariantResolvesToItsCanonicalKey() {
        EntityRules rules = rules(file("  Mechanism:\n    gene editing: [genome editing]\n  GeneTarget: {}",
                NO_EXCLUDED, PAIRS));

        assertThat(rules.canonicalKey("Mechanism", "Genome Editing")).isEqualTo("gene editing");
        assertThat(rules.canonicalKey("Mechanism", "gene-editing")).isEqualTo("gene editing");
        assertThat(rules.canonicalKey("GeneTarget", "genome editing")).isEqualTo("GENOMEEDITING");
    }

    @Test
    void everySharedKeyCaseProducesItsExpectedKey() {
        EntityRules rules = EpisodeCases.rules();
        JsonNode cases = EpisodeCases.root().get("key_cases");
        assertThat(cases.size()).isPositive();

        for (JsonNode c : cases) {
            assertThat(rules.canonicalKey(c.get("label").asText(), c.get("name").asText()))
                    .as(c.toString())
                    .isEqualTo(c.get("key").asText());
        }
    }

    @Test
    void excludedEntityIsReportedWithTheBroadEntityReason() {
        EntityRules rules = rules(file(NO_SYNONYMS, "  Mechanism: [gene therapy]\n  GeneTarget: []", PAIRS));

        assertThat(rules.excludedReason("Mechanism", "gene therapy")).contains("broad_entity");
        assertThat(rules.excludedReason("Mechanism", "base editing")).isEmpty();
        assertThat(rules.excludedReason("GeneTarget", "gene therapy")).isEmpty();
    }

    @Test
    void rulesFileWithAVariantUnderTwoCanonicalKeysIsRefused() {
        String synonyms = "  Mechanism:\n    gene editing: [genome editing]\n    base editing: [genome editing]\n  GeneTarget: {}";

        assertThatThrownBy(() -> rules(file(synonyms, NO_EXCLUDED, PAIRS)))
                .isInstanceOf(InvalidEntityRulesException.class)
                .hasMessageContaining("genome editing");
    }

    @Test
    void rulesFileWithANameNotInCanonicalFormIsRefused() {
        assertThatThrownBy(() -> rules(file(NO_SYNONYMS, "  Mechanism: [CRISPR-Cas9]\n  GeneTarget: []", PAIRS)))
                .isInstanceOf(InvalidEntityRulesException.class)
                .hasMessageContaining("canonical form");
        assertThatThrownBy(() -> rules(file("  Mechanism: {}\n  GeneTarget:\n    IL2: [il-2]", NO_EXCLUDED, PAIRS)))
                .isInstanceOf(InvalidEntityRulesException.class)
                .hasMessageContaining("canonical form");
    }

    @Test
    void rulesFileNamingAnUnknownSourceTypeIsRefused() {
        assertThatThrownBy(() -> rules(file(NO_SYNONYMS, NO_EXCLUDED, "[[biorxiv, arxiv]]")))
                .isInstanceOf(InvalidEntityRulesException.class)
                .hasMessageContaining("arxiv");
    }

    @Test
    void committedRulesFileLoadsAndExcludesTheSixMechanismsSeenInLiveData() throws IOException {
        EntityRules rules = EntityRules.load(Files.readAllBytes(COMMITTED), applicationSourceTypes());

        for (String seen : List.of("gene therapy", "aav gene therapy", "aav", "gene editing", "crispr cas9",
                "crispr cas12a")) {
            assertThat(rules.isExcluded("Mechanism", seen)).as(seen).isTrue();
        }
        assertThat(rules.canonicalKey("Mechanism", "Genome editing")).isEqualTo("gene editing");
        assertThat(rules.canonicalKey("Mechanism", "CRISPR/Cas9")).isEqualTo("crispr cas9");
        assertThat(rules.isExcluded("Mechanism", "base editing")).isFalse();
    }

    @Test
    void rulesHashIsTheSha256OfTheFileBytes() throws Exception {
        String yaml = file(NO_SYNONYMS, NO_EXCLUDED, PAIRS);
        byte[] bytes = yaml.getBytes(StandardCharsets.UTF_8);
        String expected = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));

        assertThat(rules(yaml).hash()).isEqualTo(expected);
        assertThat(rules(yaml + "# a comment changes the bytes\n").hash()).isNotEqualTo(expected);
    }

    @Test
    void configuredSourceTypesAreTheScraperSourceNames() throws IOException {
        Map<String, Object> sources = new Yaml().load(
                Files.readString(Path.of("../ingestion-scraper/config/sources.yaml")));
        @SuppressWarnings("unchecked")
        Set<String> names = ((List<Map<String, Object>>) sources.get("sources")).stream()
                .map(s -> (String) s.get("source_type")).collect(Collectors.toCollection(TreeSet::new));

        assertThat(new TreeSet<>(applicationSourceTypes())).isEqualTo(names);
    }

    @SuppressWarnings("unchecked")
    static Set<String> applicationSourceTypes() throws IOException {
        try (InputStream in = EntityRulesTest.class.getResourceAsStream("/application.yml")) {
            Map<String, Object> yml = new Yaml().load(in);
            Map<String, Object> corroboration = (Map<String, Object>) yml.get("corroboration");
            return Set.of(((String) corroboration.get("source-types")).split(","));
        }
    }
}
