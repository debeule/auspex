package dev.auspex.corehub.persistence;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/**
 * The key a company name is compared on when matching it to an SEC filer title: lower-case,
 * punctuation removed, trailing corporate suffixes stripped, whitespace collapsed. Applied to both
 * the extracted name and the SEC title, so "Sarepta Therapeutics" matches "SAREPTA THERAPEUTICS, INC.".
 */
public final class CompanyNameNormalizer {

    private static final Set<String> CORPORATE_SUFFIXES = Set.of(
            "inc", "corp", "corporation", "co", "ltd", "plc", "nv", "sa", "ag", "holdings");

    private CompanyNameNormalizer() {}

    public static String normalize(String name) {
        // Dots and apostrophes join their letters ("N.V." -> "nv"); other punctuation separates words.
        String cleaned = name.toLowerCase(Locale.ROOT)
                .replaceAll("[.'\\u2019]", "")
                .replaceAll("[^\\p{L}\\p{N}]+", " ")
                .strip();
        List<String> words = new ArrayList<>(cleaned.isEmpty() ? List.of() : Arrays.asList(cleaned.split(" ")));
        while (!words.isEmpty() && CORPORATE_SUFFIXES.contains(words.getLast())) {
            words.removeLast();
        }
        return String.join(" ", words);
    }
}
