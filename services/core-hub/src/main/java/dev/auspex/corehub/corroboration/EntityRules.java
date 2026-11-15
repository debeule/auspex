package dev.auspex.corehub.corroboration;

import org.yaml.snakeyaml.LoaderOptions;
import org.yaml.snakeyaml.Yaml;
import org.yaml.snakeyaml.constructor.SafeConstructor;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.text.Normalizer;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

/**
 * The corroboration entity rules, loaded from {@code config/corroboration/entity-rules.yaml}:
 * which names are one entity ({@code synonyms}), which entities are too broad to corroborate
 * ({@code excluded}), and which participants report one finding ({@code same_finding}).
 *
 * <p>Every name in the file must already be a canonical key; {@link #load} refuses a file that
 * breaks that or lists a source type outside the known set. The rules hash is the SHA-256 of the
 * file's bytes and is the one version of the rules.
 */
public final class EntityRules implements EntityNormalizer {

    public static final String GENE_TARGET = "GeneTarget";
    public static final String MECHANISM = "Mechanism";
    public static final String BROAD_ENTITY = "broad_entity";
    private static final List<String> LABELS = List.of(GENE_TARGET, MECHANISM);

    private final String hash;
    private final Map<String, Map<String, String>> variantToCanonical;
    private final Map<String, Set<String>> excluded;
    private final SameFinding sameFinding;

    /** Which source-type pairs can be one finding, and the title overlap that makes them one. */
    public record SameFinding(Set<Set<String>> sourceTypePairs, double titleTokenJaccardMin) {
        public boolean listsPair(String a, String b) {
            return !a.equals(b) && sourceTypePairs.contains(Set.of(a, b));
        }
    }

    private EntityRules(String hash, Map<String, Map<String, String>> variantToCanonical,
                        Map<String, Set<String>> excluded, SameFinding sameFinding) {
        this.hash = hash;
        this.variantToCanonical = variantToCanonical;
        this.excluded = excluded;
        this.sameFinding = sameFinding;
    }

    /**
     * Parses and validates the rules file.
     *
     * @throws InvalidEntityRulesException when the file is not valid
     */
    public static EntityRules load(byte[] bytes, Set<String> knownSourceTypes) {
        Object root;
        try {
            root = new Yaml(new SafeConstructor(new LoaderOptions()))
                    .load(new String(bytes, StandardCharsets.UTF_8));
        } catch (RuntimeException e) {
            throw new InvalidEntityRulesException("rules file is not YAML: " + e.getMessage());
        }
        Map<String, Object> top = map(root, "the rules file");
        Map<String, Object> synonyms = map(top.get("synonyms"), "synonyms");
        Map<String, Object> excludedRaw = map(top.get("excluded"), "excluded");
        Map<String, Object> sameFindingRaw = map(top.get("same_finding"), "same_finding");

        Map<String, Map<String, String>> variants = new HashMap<>();
        Map<String, Set<String>> excluded = new HashMap<>();
        for (String label : LABELS) {
            Map<String, String> labelVariants = new HashMap<>();
            Map<String, Object> labelSynonyms = map(synonyms.getOrDefault(label, Map.of()), "synonyms." + label);
            for (Map.Entry<String, Object> entry : labelSynonyms.entrySet()) {
                String canonical = requireCanonical(label, entry.getKey());
                for (Object v : list(entry.getValue(), "synonyms." + label + "." + canonical)) {
                    String variant = requireCanonical(label, string(v, "a variant of " + canonical));
                    String previous = labelVariants.put(variant, canonical);
                    if (previous != null) {
                        throw new InvalidEntityRulesException(
                                "variant '" + variant + "' is listed under '" + previous + "' and '" + canonical + "'");
                    }
                }
            }
            for (String canonical : labelSynonyms.keySet()) {
                if (labelVariants.containsKey(canonical)) {
                    throw new InvalidEntityRulesException("canonical key '" + canonical + "' is also a variant");
                }
            }
            Set<String> labelExcluded = new LinkedHashSet<>();
            for (Object e : list(excludedRaw.getOrDefault(label, List.of()), "excluded." + label)) {
                String name = requireCanonical(label, string(e, "an excluded name"));
                if (labelVariants.containsKey(name)) {
                    throw new InvalidEntityRulesException("excluded name '" + name + "' is a variant");
                }
                labelExcluded.add(name);
            }
            variants.put(label, Map.copyOf(labelVariants));
            excluded.put(label, Set.copyOf(labelExcluded));
        }
        for (String key : synonyms.keySet()) {
            requireLabel(key, "synonyms");
        }
        for (String key : excludedRaw.keySet()) {
            requireLabel(key, "excluded");
        }

        Set<Set<String>> pairs = new LinkedHashSet<>();
        for (Object p : list(sameFindingRaw.get("source_type_pairs"), "same_finding.source_type_pairs")) {
            List<Object> pair = list(p, "a source type pair");
            if (pair.size() != 2) {
                throw new InvalidEntityRulesException("a source type pair has " + pair.size() + " entries");
            }
            Set<String> types = new LinkedHashSet<>();
            for (Object t : pair) {
                String type = string(t, "a source type");
                if (!knownSourceTypes.contains(type)) {
                    throw new InvalidEntityRulesException("unknown source type '" + type + "'");
                }
                types.add(type);
            }
            if (types.size() != 2) {
                throw new InvalidEntityRulesException("a source type pair names one type twice");
            }
            pairs.add(Set.copyOf(types));
        }
        Object threshold = sameFindingRaw.get("title_token_jaccard_min");
        if (!(threshold instanceof Number number)) {
            throw new InvalidEntityRulesException("same_finding.title_token_jaccard_min is not a number");
        }
        double min = number.doubleValue();
        if (!(min > 0.0 && min <= 1.0)) {
            throw new InvalidEntityRulesException("same_finding.title_token_jaccard_min " + min + " is outside (0, 1]");
        }
        return new EntityRules(sha256(bytes), variants, excluded, new SameFinding(Set.copyOf(pairs), min));
    }

    /** The canonical key of a name under the label's normalisation, before synonyms are applied. */
    public static String normalForm(String label, String name) {
        String nfkc = Normalizer.normalize(name, Normalizer.Form.NFKC);
        StringBuilder out = new StringBuilder();
        if (GENE_TARGET.equals(label)) {
            nfkc.toUpperCase(Locale.ROOT).codePoints()
                    .filter(Character::isLetterOrDigit)
                    .forEach(out::appendCodePoint);
            return out.toString();
        }
        if (MECHANISM.equals(label)) {
            return tokens(nfkc.toLowerCase(Locale.ROOT));
        }
        throw new IllegalArgumentException("not a corroborating label: " + label);
    }

    /** Lower-cased text with every run of characters that are not letters or digits as one space, trimmed. */
    static String tokens(String lowerCased) {
        StringBuilder out = new StringBuilder();
        boolean gap = false;
        for (int cp : (Iterable<Integer>) lowerCased.codePoints()::iterator) {
            if (Character.isLetterOrDigit(cp)) {
                if (gap && !out.isEmpty()) {
                    out.append(' ');
                }
                out.appendCodePoint(cp);
                gap = false;
            } else {
                gap = true;
            }
        }
        return out.toString();
    }

    /** The canonical key of a name: its normal form, replaced by its canonical key when it is a variant. */
    public String canonicalKey(String label, String name) {
        String normal = normalForm(label, name);
        return variantToCanonical.get(label).getOrDefault(normal, normal);
    }

    @Override
    public String normalize(String label, String name) {
        return canonicalKey(label, name);
    }

    public boolean isExcluded(String label, String canonicalKey) {
        return excluded.getOrDefault(label, Set.of()).contains(canonicalKey);
    }

    /** {@code broad_entity} for an excluded entity, otherwise empty. */
    public Optional<String> excludedReason(String label, String canonicalKey) {
        return isExcluded(label, canonicalKey) ? Optional.of(BROAD_ENTITY) : Optional.empty();
    }

    public SameFinding sameFinding() {
        return sameFinding;
    }

    public String hash() {
        return hash;
    }

    private static String requireCanonical(String label, String name) {
        if (!normalForm(label, name).equals(name)) {
            throw new InvalidEntityRulesException(
                    label + " name '" + name + "' is not in canonical form ('" + normalForm(label, name) + "')");
        }
        return name;
    }

    private static void requireLabel(String key, String section) {
        if (!LABELS.contains(key)) {
            throw new InvalidEntityRulesException(section + " names an unknown label '" + key + "'");
        }
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> map(Object value, String what) {
        if (value == null) {
            return Map.of();
        }
        if (!(value instanceof Map<?, ?> m)) {
            throw new InvalidEntityRulesException(what + " is not a mapping");
        }
        for (Object k : m.keySet()) {
            if (!(k instanceof String)) {
                throw new InvalidEntityRulesException(what + " has a key that is not text: " + k);
            }
        }
        return (Map<String, Object>) m;
    }

    private static List<Object> list(Object value, String what) {
        if (value == null) {
            throw new InvalidEntityRulesException(what + " is missing");
        }
        if (!(value instanceof List<?> l)) {
            throw new InvalidEntityRulesException(what + " is not a list");
        }
        return new ArrayList<>(l);
    }

    private static String string(Object value, String what) {
        if (!(value instanceof String s)) {
            throw new InvalidEntityRulesException(what + " is not text: " + value);
        }
        return s;
    }

    static String sha256(byte[] bytes) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 not available", e);
        }
    }
}
