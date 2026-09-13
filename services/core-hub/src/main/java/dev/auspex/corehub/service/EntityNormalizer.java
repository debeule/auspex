package dev.auspex.corehub.service;

/**
 * Normalizes entity names to a canonical form for corroboration matching.
 */
public interface EntityNormalizer {
    String normalize(String name);
}
