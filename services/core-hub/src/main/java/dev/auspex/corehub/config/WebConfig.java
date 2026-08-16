package dev.auspex.corehub.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.http.converter.HttpMessageConverter;
import org.springframework.http.converter.json.MappingJackson2HttpMessageConverter;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.util.List;
import java.util.ListIterator;

@Configuration
class WebConfig implements WebMvcConfigurer {

    private final ObjectMapper objectMapper;

    WebConfig(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/api/**")
                .allowedOrigins("*")
                .allowedMethods("GET");
    }

    // Boot 4.1 auto-configures a Jackson 3.x mapper for MVC; replace it with our
    // Jackson 2.x mapper so that HTTP responses use SNAKE_CASE and ISO-8601 timestamps.
    @Override
    public void extendMessageConverters(List<HttpMessageConverter<?>> converters) {
        ListIterator<HttpMessageConverter<?>> it = converters.listIterator();
        while (it.hasNext()) {
            if (it.next() instanceof MappingJackson2HttpMessageConverter) {
                it.set(new MappingJackson2HttpMessageConverter(objectMapper));
                return;
            }
        }
        converters.add(0, new MappingJackson2HttpMessageConverter(objectMapper));
    }
}
