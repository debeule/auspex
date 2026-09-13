package dev.auspex.corehub.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableScheduling;

import java.time.Clock;

@Configuration
@EnableScheduling
class SchedulingConfig {

    @Bean
    Clock clock() {
        return Clock.systemUTC();
    }
}
