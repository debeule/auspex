package dev.auspex.corehub.corroboration;

/** One corroborating entity: a node label and the canonical key its nodes share. */
public record EntityRef(String label, String key) {

    /** {@code <canonical key>:<label>}, for example {@code BCL11A:GeneTarget}. */
    public String entityKey() {
        return key + ":" + label;
    }

    /** Reads an {@code entity_key}; a canonical key never holds a colon, so the label follows the last one. */
    public static EntityRef parse(String entityKey) {
        int colon = entityKey.lastIndexOf(':');
        if (colon < 0) {
            throw new IllegalArgumentException("not an entity key: " + entityKey);
        }
        return new EntityRef(entityKey.substring(colon + 1), entityKey.substring(0, colon));
    }
}
