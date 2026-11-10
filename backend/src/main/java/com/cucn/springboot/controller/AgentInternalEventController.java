package com.cucn.springboot.controller;

import com.cucn.springboot.common.Result;
import com.cucn.springboot.dto.AgentEventRequest;
import com.cucn.springboot.service.AgentRunService;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import javax.annotation.Resource;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Map;

@RestController
@RequestMapping("/internal/agent/v1/runs")
public class AgentInternalEventController {

    @Value("${agent.service.shared-secret:}")
    private String sharedSecret;

    @Resource
    private AgentRunService agentRunService;

    @PostMapping("/{runId}/events")
    public ResponseEntity<Result> receiveEvent(
            @PathVariable String runId,
            @RequestHeader(value = "X-Agent-Service-Token", required = false) String token,
            @RequestBody AgentEventRequest request) {
        if (!isAuthorized(token)) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body(Result.error("401", "Invalid service credentials"));
        }
        try {
            String outcome = agentRunService.acceptEvent(runId, request);
            return ResponseEntity.ok(Result.success(java.util.Collections.<String, Object>singletonMap("outcome", outcome)));
        } catch (java.util.NoSuchElementException exception) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(Result.error("404", "运行记录不存在"));
        } catch (IllegalArgumentException exception) {
            HttpStatus status = "Event sequence gap".equals(exception.getMessage())
                    ? HttpStatus.CONFLICT
                    : HttpStatus.BAD_REQUEST;
            return ResponseEntity.status(status)
                    .body(Result.error(String.valueOf(status.value()), exception.getMessage()));
        }
    }

    private boolean isAuthorized(String token) {
        if (sharedSecret == null || sharedSecret.isEmpty() || token == null) {
            return false;
        }
        return MessageDigest.isEqual(
                sharedSecret.getBytes(StandardCharsets.UTF_8),
                token.getBytes(StandardCharsets.UTF_8)
        );
    }
}
