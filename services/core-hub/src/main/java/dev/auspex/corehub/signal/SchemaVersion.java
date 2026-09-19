package dev.auspex.corehub.signal;

import java.util.Set;

/**
 * Parses and compares schema_version strings as integer pairs.
 * "1.10" must be greater than "1.9" — string comparison gets this wrong.
 */
public record SchemaVersion(int major, int minor) implements Comparable<SchemaVersion> {

    private static final Set<Integer> KNOWN_MAJORS = Set.of(1);

    public static SchemaVersion parse(String version) {
        String[] parts = version.split("\\.", 2);
        return new SchemaVersion(
                Integer.parseInt(parts[0]),
                Integer.parseInt(parts[1])
        );
    }

    public static boolean isKnownMajor(SchemaVersion v) {
        return KNOWN_MAJORS.contains(v.major());
    }

    @Override
    public int compareTo(SchemaVersion other) {
        int cmp = Integer.compare(this.major, other.major);
        return cmp != 0 ? cmp : Integer.compare(this.minor, other.minor);
    }
}
