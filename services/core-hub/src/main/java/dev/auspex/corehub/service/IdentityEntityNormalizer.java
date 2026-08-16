package dev.auspex.corehub.service;

import org.springframework.stereotype.Component;

@Component
class IdentityEntityNormalizer implements EntityNormalizer {
    @Override
    public String normalize(String name) {
        return name;
    }
}
