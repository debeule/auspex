package dev.auspex.corehub.corroboration;

/** Maps an entity node's name to the canonical key two nodes of one label share when they are one entity. */
public interface EntityNormalizer {
    String normalize(String label, String name);
}
