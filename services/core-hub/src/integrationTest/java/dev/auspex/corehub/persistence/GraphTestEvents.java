package dev.auspex.corehub.persistence;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import dev.auspex.corehub.TestFixtures;
import dev.auspex.corehub.signal.ResearchSignalEvent;

import java.util.List;
import java.util.UUID;

/** Builds signal events from the contract fixture with the entities a graph test needs. */
final class GraphTestEvents {

    private final ObjectMapper objectMapper;

    GraphTestEvents(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    ResearchSignalEvent event(String sourceType, List<String> geneTargets, List<String> mechanisms,
                              List<String> companies) {
        return event(UUID.randomUUID(), sourceType, geneTargets, mechanisms, companies);
    }

    /** A fresh extraction of {@code eventId}: a new extraction id, the same document. */
    ResearchSignalEvent event(UUID eventId, String sourceType, List<String> geneTargets, List<String> mechanisms,
                              List<String> companies) {
        try {
            return objectMapper.treeToValue(json(eventId, sourceType, geneTargets, mechanisms, companies),
                    ResearchSignalEvent.class);
        } catch (Exception ex) {
            throw new IllegalStateException(ex);
        }
    }

    ObjectNode json(UUID uuid, String sourceType, List<String> geneTargets, List<String> mechanisms,
                    List<String> companies) {
        try {
            ObjectNode node = (ObjectNode) objectMapper.readTree(TestFixtures.validSignalJson());
            String eventId = uuid.toString();
            node.put("event_id", eventId);
            node.put("extraction_id", UUID.randomUUID().toString());
            node.put("external_id", "ext-" + eventId);
            node.put("source_type", sourceType);
            node.put("raw_object_key", "raw/" + sourceType + "/ext-" + eventId + "/20240615T120000Z-abcdef12.json");
            node.set("gene_targets", array(geneTargets));
            node.set("mechanisms", array(mechanisms));
            node.set("companies_mentioned", array(companies));
            return node;
        } catch (Exception ex) {
            throw new IllegalStateException(ex);
        }
    }

    private ArrayNode array(List<String> values) {
        ArrayNode array = objectMapper.createArrayNode();
        values.forEach(array::add);
        return array;
    }
}
