package dev.auspex.corehub.corroboration;

/**
 * Normalizes entity names to a canonical form for corroboration matching.
 */
public interface EntityNormalizer {
    String normalize(String name);
}
