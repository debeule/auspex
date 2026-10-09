package dev.auspex.corehub.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import dev.auspex.corehub.rest.dto.ErrorResponse;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.web.servlet.HandlerInterceptor;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Set;

/**
 * Requires {@code Authorization: Bearer <token>} on every API request that is not a GET or HEAD.
 * The dashboard's server layer is the only intended writer. With no token configured every write
 * is refused, so a missing secret fails closed.
 */
class WriteTokenInterceptor implements HandlerInterceptor {

    private static final Set<String> READ_METHODS = Set.of("GET", "HEAD");

    private final byte[] expectedHeader;
    private final ObjectMapper objectMapper;

    WriteTokenInterceptor(String token, ObjectMapper objectMapper) {
        this.expectedHeader = token == null || token.isBlank()
                ? null
                : ("Bearer " + token).getBytes(StandardCharsets.UTF_8);
        this.objectMapper = objectMapper;
    }

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler)
            throws Exception {
        if (READ_METHODS.contains(request.getMethod())) {
            return true;
        }
        String header = request.getHeader(HttpHeaders.AUTHORIZATION);
        if (expectedHeader != null && header != null
                && MessageDigest.isEqual(header.getBytes(StandardCharsets.UTF_8), expectedHeader)) {
            return true;
        }
        response.setStatus(HttpStatus.UNAUTHORIZED.value());
        response.setHeader(HttpHeaders.WWW_AUTHENTICATE, "Bearer");
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        objectMapper.writeValue(response.getOutputStream(),
                new ErrorResponse("Writes need the core-hub write token", HttpStatus.UNAUTHORIZED.value()));
        return false;
    }
}
