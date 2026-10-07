package dev.auspex.corehub;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.WebApplicationContext;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.UUID;

import static org.hamcrest.Matchers.hasSize;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/** Lineage overlap the historical backfill's dry run asks for. */
class ExtractionLineageIT extends AbstractIT {

    @Autowired
    WebApplicationContext webApplicationContext;

    MockMvc mockMvc;

    @BeforeEach
    void setupMockMvc() {
        mockMvc = MockMvcBuilders.webAppContextSetup(webApplicationContext).build();
    }

    private void insertExtraction(String sourceType, String publishedAt, String... models) {
        UUID eventId = UUID.randomUUID();
        String currentModel = models[models.length - 1];
        UUID currentExtraction = UUID.randomUUID();
        jdbcTemplate.update("""
                INSERT INTO signal_current (event_id, extraction_id, schema_version, source_type, source_url,
                    external_id, raw_object_key, published_date, published_date_field, ingested_at, title,
                    raw_text_snippet, gene_targets, mechanisms, companies_mentioned, summary, directionality,
                    confidence_score, prompt_version, prefilter_version, extraction_model)
                VALUES (?, ?, '1.0', ?, 'https://example.com', ?, 'raw/k.json', ?, 'published_date', now(),
                    't', 's', '{}', '{}', '{}', 's', 'neutral', 0.5, 'v1.0', 'v1.0', ?)
                """,
                eventId, currentExtraction, sourceType, "ext-" + eventId,
                Timestamp.from(Instant.parse(publishedAt)), currentModel);
        for (String model : models) {
            UUID extractionId = model.equals(currentModel) ? currentExtraction : UUID.randomUUID();
            jdbcTemplate.update("""
                    INSERT INTO signal_extraction_history (event_id, extraction_id, schema_version,
                        confidence_score, prompt_version, prefilter_version, extraction_model)
                    VALUES (?, ?, '1.0', 0.5, 'v1.0', 'v1.0', ?)
                    """, eventId, extractionId, model);
        }
    }

    @Test
    void test_extraction_models_counts_documents_per_model_within_window_and_source() throws Exception {
        insertExtraction("biorxiv", "2025-01-01T00:00:00Z", "gpt-4o-mini-2024-07-18");
        insertExtraction("biorxiv", "2025-01-31T23:59:59Z", "gpt-4o-mini-2024-07-18", "llama3.1:8b");
        insertExtraction("biorxiv", "2025-02-01T00:00:00Z", "gpt-4o-mini-2024-07-18"); // after window
        insertExtraction("biorxiv", "2024-12-31T23:59:59Z", "gpt-4o-mini-2024-07-18"); // before window
        insertExtraction("pubmed", "2025-01-15T00:00:00Z", "gpt-4o-mini-2024-07-18");  // other source

        mockMvc.perform(get("/api/v1/extractions/models")
                        .param("source_type", "biorxiv")
                        .param("from", "2025-01-01")
                        .param("to", "2025-01-31"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$", hasSize(2)))
                .andExpect(jsonPath("$[0].extraction_model").value("gpt-4o-mini-2024-07-18"))
                .andExpect(jsonPath("$[0].documents").value(2))
                .andExpect(jsonPath("$[1].extraction_model").value("llama3.1:8b"))
                .andExpect(jsonPath("$[1].documents").value(1));
    }

    @Test
    void test_extraction_models_rejects_inverted_window() throws Exception {
        mockMvc.perform(get("/api/v1/extractions/models")
                        .param("source_type", "biorxiv")
                        .param("from", "2025-02-01")
                        .param("to", "2025-01-01"))
                .andExpect(status().isBadRequest());
    }
}
