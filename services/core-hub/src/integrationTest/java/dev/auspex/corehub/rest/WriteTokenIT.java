package dev.auspex.corehub.rest;

import dev.auspex.corehub.AbstractIT;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.WebApplicationContext;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.options;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class WriteTokenIT extends AbstractIT {

    private static final String ADD_BODY = """
            {"ticker":"SRPT","company_name":"Sarepta Therapeutics","gene_targets":[]}
            """;

    @Autowired
    WebApplicationContext webApplicationContext;

    @Value("${auspex.api.write-token}")
    String writeToken;

    MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        mockMvc = MockMvcBuilders.webAppContextSetup(webApplicationContext).build();
        jdbcTemplate.execute("TRUNCATE watchlist CASCADE");
    }

    private static MockHttpServletRequestBuilder addRequest() {
        return post("/api/v1/watchlist").contentType(MediaType.APPLICATION_JSON).content(ADD_BODY);
    }

    private int watchlistRows() {
        return jdbcTemplate.queryForObject("SELECT count(*) FROM watchlist", Integer.class);
    }

    @Test
    void writeWithoutTokenIsRejectedWith401() throws Exception {
        mockMvc.perform(addRequest())
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.status").value(401));
        jdbcTemplate.update("INSERT INTO watchlist (ticker, company_name) VALUES ('BEAM', 'Beam Therapeutics')");
        mockMvc.perform(delete("/api/v1/watchlist/BEAM")).andExpect(status().isUnauthorized());
        mockMvc.perform(patch("/api/v1/watchlist/BEAM/gene-targets")
                        .contentType(MediaType.APPLICATION_JSON).content("{\"add\":[\"BCL11A\"]}"))
                .andExpect(status().isUnauthorized());

        assertThat(watchlistRows()).isEqualTo(1);
        assertThat(jdbcTemplate.queryForObject("SELECT count(*) FROM watchlist_gene_target", Integer.class)).isZero();
    }

    @Test
    void writeWithWrongTokenIsRejectedWith401() throws Exception {
        mockMvc.perform(addRequest().header(HttpHeaders.AUTHORIZATION, "Bearer " + writeToken + "x"))
                .andExpect(status().isUnauthorized());
        mockMvc.perform(addRequest().header(HttpHeaders.AUTHORIZATION, writeToken))
                .andExpect(status().isUnauthorized());
        mockMvc.perform(addRequest().header(HttpHeaders.AUTHORIZATION, "Bearer "))
                .andExpect(status().isUnauthorized());

        assertThat(watchlistRows()).isZero();
    }

    @Test
    void writeWithTokenSucceeds() throws Exception {
        mockMvc.perform(addRequest().header(HttpHeaders.AUTHORIZATION, "Bearer " + writeToken))
                .andExpect(status().isCreated());
        mockMvc.perform(patch("/api/v1/watchlist/SRPT/gene-targets")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + writeToken)
                        .contentType(MediaType.APPLICATION_JSON).content("{\"add\":[\"DMD\"]}"))
                .andExpect(status().isOk());
        mockMvc.perform(delete("/api/v1/watchlist/SRPT").header(HttpHeaders.AUTHORIZATION, "Bearer " + writeToken))
                .andExpect(status().isNoContent());

        assertThat(watchlistRows()).isZero();
    }

    @Test
    void getRequestsNeedNoToken() throws Exception {
        mockMvc.perform(get("/api/v1/watchlist")).andExpect(status().isOk());
        mockMvc.perform(get("/api/v1/signals/BEAM")).andExpect(status().isOk());
    }

    @Test
    void noCorsHeadersAreReturnedForCrossOriginRequests() throws Exception {
        mockMvc.perform(get("/api/v1/watchlist").header(HttpHeaders.ORIGIN, "http://evil.example"))
                .andExpect(header().doesNotExist(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN));
        mockMvc.perform(options("/api/v1/watchlist")
                        .header(HttpHeaders.ORIGIN, "http://evil.example")
                        .header(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, "POST"))
                .andExpect(header().doesNotExist(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN))
                .andExpect(header().doesNotExist(HttpHeaders.ACCESS_CONTROL_ALLOW_METHODS));
    }
}
