package dev.auspex.corehub.corroboration;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.io.Resource;

import java.io.IOException;
import java.io.InputStream;
import java.util.Arrays;
import java.util.Set;
import java.util.stream.Collectors;

/** Loads the entity rules file named by {@code corroboration.rules-file}; core-hub does not start without a valid one. */
@Configuration
class CorroborationRulesConfig {

    @Bean
    EntityRules entityRules(@Value("${corroboration.rules-file}") Resource rulesFile,
                            @Value("${corroboration.source-types}") String sourceTypes) {
        Set<String> known = Arrays.stream(sourceTypes.split(",")).map(String::trim)
                .filter(s -> !s.isEmpty()).collect(Collectors.toUnmodifiableSet());
        if (!rulesFile.exists()) {
            throw new InvalidEntityRulesException("corroboration rules file not found: " + rulesFile.getDescription());
        }
        try (InputStream in = rulesFile.getInputStream()) {
            return EntityRules.load(in.readAllBytes(), known);
        } catch (IOException e) {
            throw new InvalidEntityRulesException("corroboration rules file unreadable: " + e.getMessage());
        }
    }
}
