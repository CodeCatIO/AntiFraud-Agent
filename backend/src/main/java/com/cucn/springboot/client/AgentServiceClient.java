package com.cucn.springboot.client;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

import javax.annotation.Resource;
import java.util.HashMap;
import java.util.Map;

@Component
public class AgentServiceClient {

    @Value("${agent.service.base-url:http://localhost:8001}")
    private String baseUrl;

    @Value("${agent.service.shared-secret:}")
    private String sharedSecret;

    @Resource
    @Qualifier("aiServiceRestTemplate")
    private RestTemplate restTemplate;

    public void startRun(String runId, Long caseId, Integer ownerId, String content) {
        Map<String, Object> body = new HashMap<>();
        body.put("runId", runId);
        body.put("caseId", caseId);
        body.put("ownerId", ownerId);
        body.put("content", content);

        post("/internal/v1/runs", body);
    }

    public void supplementRun(String runId, Integer round, Map<String, String> answers) {
        Map<String, Object> body = new HashMap<>();
        body.put("round", round);
        body.put("answers", answers);
        post("/internal/v1/runs/" + runId + "/supplement", body);
    }

    public void reviewRun(
            String runId,
            Integer reviewerId,
            String decision,
            String comment,
            Map<String, Object> edits) {
        Map<String, Object> body = new HashMap<>();
        body.put("reviewerId", reviewerId);
        body.put("decision", decision);
        body.put("comment", comment);
        body.put("edits", edits);
        post("/internal/v1/runs/" + runId + "/review", body);
    }

    private void post(String path, Map<String, Object> body) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set("X-Agent-Service-Token", sharedSecret);
        HttpEntity<Map<String, Object>> entity = new HttpEntity<>(body, headers);
        ResponseEntity<Map> response = restTemplate.exchange(
                baseUrl + path,
                HttpMethod.POST,
                entity,
                Map.class
        );
        if (!response.getStatusCode().is2xxSuccessful()) {
            throw new IllegalStateException("Agent service rejected the run");
        }
    }
}
