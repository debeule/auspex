package dev.auspex.corehub.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import static org.assertj.core.api.Assertions.assertThat;

class WriteTokenInterceptorTest {

    private final ObjectMapper objectMapper = new ObjectMapper();

    private static MockHttpServletRequest request(String method, String authorization) {
        MockHttpServletRequest request = new MockHttpServletRequest(method, "/api/v1/watchlist");
        if (authorization != null) request.addHeader("Authorization", authorization);
        return request;
    }

    private boolean admits(String configuredToken, String method, String authorization) throws Exception {
        return new WriteTokenInterceptor(configuredToken, objectMapper)
                .preHandle(request(method, authorization), new MockHttpServletResponse(), new Object());
    }

    @Test
    void test_reads_pass_without_a_token() throws Exception {
        assertThat(admits("s3cret", "GET", null)).isTrue();
        assertThat(admits("s3cret", "HEAD", null)).isTrue();
    }

    @Test
    void test_writes_need_the_exact_bearer_token() throws Exception {
        for (String method : new String[] {"POST", "PUT", "PATCH", "DELETE", "OPTIONS"}) {
            assertThat(admits("s3cret", method, "Bearer s3cret")).as(method).isTrue();
            assertThat(admits("s3cret", method, null)).as(method).isFalse();
            assertThat(admits("s3cret", method, "Bearer s3cre")).as(method).isFalse();
            assertThat(admits("s3cret", method, "Bearer s3cretx")).as(method).isFalse();
            assertThat(admits("s3cret", method, "s3cret")).as(method).isFalse();
            assertThat(admits("s3cret", method, "Basic s3cret")).as(method).isFalse();
        }
    }

    @Test
    void test_writes_are_refused_when_no_token_is_configured() throws Exception {
        for (String configured : new String[] {null, "", "   "}) {
            assertThat(admits(configured, "POST", "Bearer ")).isFalse();
            assertThat(admits(configured, "POST", "Bearer " + configured)).isFalse();
            assertThat(admits(configured, "GET", null)).isTrue();
        }
    }

    @Test
    void test_rejection_is_a_401_json_error() throws Exception {
        MockHttpServletResponse response = new MockHttpServletResponse();

        new WriteTokenInterceptor("s3cret", objectMapper).preHandle(request("POST", null), response, new Object());

        assertThat(response.getStatus()).isEqualTo(401);
        assertThat(response.getHeader("WWW-Authenticate")).isEqualTo("Bearer");
        assertThat(response.getContentType()).startsWith("application/json");
        var body = objectMapper.readTree(response.getContentAsString());
        assertThat(body.get("status").asInt()).isEqualTo(401);
        assertThat(body.get("message").asText()).isNotBlank();
    }
}
