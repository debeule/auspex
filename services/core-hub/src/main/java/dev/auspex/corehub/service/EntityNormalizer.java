package dev.auspex.corehub.service;

/**
 * Normalizes entity names to a canonical form for corroboration matching.
 * Phase 1 ships the identity implementation. Phase 2 substitutes a real normalizer (§6.4).
 */
public interface EntityNormalizer {
    String normalize(String name);
}
