package dev.auspex.corehub.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.converter.HttpMessageConverter;
import org.springframework.http.converter.json.MappingJackson2HttpMessageConverter;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.util.List;
import java.util.ListIterator;

@Configuration
class WebConfig implements WebMvcConfigurer {

    private static final Logger log = LoggerFactory.getLogger(WebConfig.class);

    private final ObjectMapper objectMapper;
    private final String writeToken;

    WebConfig(ObjectMapper objectMapper, @Value("${auspex.api.write-token:}") String writeToken) {
        this.objectMapper = objectMapper;
        this.writeToken = writeToken;
        if (writeToken.isBlank()) {
            log.warn("CORE_HUB_WRITE_TOKEN is not set; every write under /api will be refused");
        }
    }

    // No CORS mappings: browsers reach core-hub only through the dashboard's server, never directly.
    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(new WriteTokenInterceptor(writeToken, objectMapper)).addPathPatterns("/api/**");
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
