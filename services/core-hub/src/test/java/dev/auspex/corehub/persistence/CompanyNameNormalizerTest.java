package dev.auspex.corehub.persistence;

import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.ValueSource;

import static org.assertj.core.api.Assertions.assertThat;

class CompanyNameNormalizerTest {

    @ParameterizedTest
    @CsvSource(delimiter = '|', value = {
            "Sarepta Therapeutics, Inc.      | sarepta therapeutics",
            "SAREPTA THERAPEUTICS INC        | sarepta therapeutics",
            "Beam Therapeutics Inc.          | beam therapeutics",
            "uniQure N.V.                    | uniqure",
            "Rocket Pharmaceuticals Corp     | rocket pharmaceuticals",
            "Acme Holdings Co., Ltd.         | acme",
            "Novartis AG                     | novartis",
            "Sanofi SA                       | sanofi",
            "GSK plc                         | gsk",
            "Pfizer Corporation              | pfizer",
            "'  Bluebird   bio,  Inc. '      | bluebird bio",
            "Intellia Therapeutics           | intellia therapeutics",
    })
    void corporateSuffixesAndPunctuationAreStripped(String raw, String expected) {
        assertThat(CompanyNameNormalizer.normalize(raw)).isEqualTo(expected);
    }

    @ParameterizedTest
    @ValueSource(strings = {"Sarepta Therapeutics, Inc.", "uniQure N.V.", "Acme Holdings Co., Ltd.", "Inc", ""})
    void normalizationIsIdempotent(String raw) {
        String once = CompanyNameNormalizer.normalize(raw);
        assertThat(CompanyNameNormalizer.normalize(once)).isEqualTo(once);
    }
}
