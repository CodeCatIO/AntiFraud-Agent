package com.cucn.springboot.service;

import com.cucn.springboot.client.AgentServiceClient;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClientException;

import javax.annotation.Resource;
import java.util.Map;

@Slf4j
@Service
public class AgentRunDispatcher {

    @Resource
    private AgentServiceClient agentServiceClient;

    @Resource
    private AgentRunService agentRunService;

    @Async("aiDetectionExecutor")
    public void dispatch(String runId, Long caseId, Integer ownerId, String content) {
        try {
            agentServiceClient.startRun(runId, caseId, ownerId, content);
        } catch (RestClientException exception) {
            log.warn("Agent service dispatch failed for run {}", runId);
            agentRunService.markDispatchFailed(runId, "AGENT_SERVICE_UNAVAILABLE");
        } catch (Exception exception) {
            log.error("Unexpected Agent dispatch failure for run {}", runId);
            agentRunService.markDispatchFailed(runId, "AGENT_DISPATCH_FAILED");
        }
    }

    @Async("aiDetectionExecutor")
    public void dispatchSupplement(String runId, Integer round, Map<String, String> answers) {
        try {
            agentServiceClient.supplementRun(runId, round, answers);
        } catch (RestClientException exception) {
            log.warn("Agent supplement dispatch failed for run {}", runId);
            agentRunService.markDispatchFailed(runId, "AGENT_RESUME_UNAVAILABLE");
        } catch (Exception exception) {
            log.error("Unexpected Agent supplement dispatch failure for run {}", runId);
            agentRunService.markDispatchFailed(runId, "AGENT_RESUME_FAILED");
        }
    }

    @Async("aiDetectionExecutor")
    public void dispatchReview(
            String runId,
            Integer reviewerId,
            String decision,
            String comment,
            Map<String, Object> edits) {
        try {
            agentServiceClient.reviewRun(runId, reviewerId, decision, comment, edits);
        } catch (RestClientException exception) {
            log.warn("Agent review dispatch failed for run {}", runId);
            agentRunService.markDispatchFailed(runId, "AGENT_RESUME_UNAVAILABLE");
        } catch (Exception exception) {
            log.error("Unexpected Agent review dispatch failure for run {}", runId);
            agentRunService.markDispatchFailed(runId, "AGENT_RESUME_FAILED");
        }
    }
}
