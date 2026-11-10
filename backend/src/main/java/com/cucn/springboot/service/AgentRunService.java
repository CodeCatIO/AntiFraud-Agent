package com.cucn.springboot.service;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.cucn.springboot.common.RoleEnum;
import com.cucn.springboot.dto.AgentEventRequest;
import com.cucn.springboot.entity.AgentCaseRecord;
import com.cucn.springboot.entity.AgentEventRecord;
import com.cucn.springboot.entity.AgentReviewRecord;
import com.cucn.springboot.entity.AgentRunRecord;
import com.cucn.springboot.entity.AgentSupplementRecord;
import com.cucn.springboot.mapper.AgentCaseMapper;
import com.cucn.springboot.mapper.AgentEventMapper;
import com.cucn.springboot.mapper.AgentReviewMapper;
import com.cucn.springboot.mapper.AgentRunMapper;
import com.cucn.springboot.mapper.AgentSupplementMapper;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import javax.annotation.Resource;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.OffsetDateTime;
import java.util.*;

@Service
public class AgentRunService {

    private static final Set<String> ALLOWED_STATUSES = new HashSet<>(Arrays.asList(
            "RUNNING", "WAITING_FOR_INFO", "WAITING_FOR_REVIEW",
            "COMPLETED", "PARTIAL", "FAILED", "CANCELLED", "RETURNED"
    ));
    private static final Set<String> ALLOWED_REVIEW_EDITS = new HashSet<>(Arrays.asList(
            "summary", "missingInformation", "suggestedChecks", "uncertaintyNotes"
    ));
    private static final Set<String> ALLOWED_SUPPLEMENT_FIELDS = new HashSet<>(Arrays.asList(
            "contact_channel", "claimed_identity", "requested_action", "event_time"
    ));

    @Resource
    private AgentCaseMapper caseMapper;

    @Resource
    private AgentRunMapper runMapper;

    @Resource
    private AgentEventMapper eventMapper;

    @Resource
    private AgentReviewMapper reviewMapper;

    @Resource
    private AgentSupplementMapper supplementMapper;

    @Resource
    private ObjectMapper objectMapper;

    @Transactional
    public Map<String, Object> createCaseAndRun(Integer userId, String content, String source) {
        AgentCaseRecord agentCase = new AgentCaseRecord();
        agentCase.setCaseNo(UUID.randomUUID().toString());
        agentCase.setUserId(userId);
        agentCase.setContent(content);
        agentCase.setSource(source);
        agentCase.setStatus("RUNNING");
        caseMapper.insert(agentCase);

        String runId = UUID.randomUUID().toString();
        AgentRunRecord run = new AgentRunRecord();
        run.setRunId(runId);
        run.setCaseId(agentCase.getId());
        run.setStatus("QUEUED");
        run.setLastEventSeq(0);
        run.setConfigVersion("i1");
        run.setInputHash(sha256(content));
        runMapper.insert(run);

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("caseId", agentCase.getId());
        result.put("caseNo", agentCase.getCaseNo());
        result.put("runId", runId);
        result.put("status", run.getStatus());
        return result;
    }

    public Map<String, Object> getRunForUser(String runId, Integer userId) {
        return getRunForUser(runId, userId, "ROLE_WORKER");
    }

    public Map<String, Object> getRunForUser(String runId, Integer userId, String role) {
        AgentRunRecord run = runMapper.selectOne(new QueryWrapper<AgentRunRecord>()
                .eq("run_id", runId));
        if (run == null) {
            return null;
        }
        AgentCaseRecord agentCase = caseMapper.selectOne(new QueryWrapper<AgentCaseRecord>()
                .eq("id", run.getCaseId()));
        if (agentCase == null || (!userId.equals(agentCase.getUserId()) && !canReview(role))) {
            return null;
        }

        List<AgentEventRecord> events = eventMapper.selectList(new QueryWrapper<AgentEventRecord>()
                .eq("run_id", runId)
                .orderByAsc("event_seq"));
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("caseId", agentCase.getId());
        result.put("caseNo", agentCase.getCaseNo());
        result.put("content", agentCase.getContent());
        result.put("source", agentCase.getSource());
        result.put("runId", run.getRunId());
        result.put("status", run.getStatus());
        result.put("errorCode", run.getErrorCode());
        result.put("result", parseJson(run.getResultJson()));
        result.put("events", events);
        result.put("reviews", reviewMapper.selectList(new QueryWrapper<AgentReviewRecord>()
                .eq("run_id", runId)
                .orderByAsc("created_at")));
        result.put("supplements", supplementMapper.selectList(new QueryWrapper<AgentSupplementRecord>()
                .eq("run_id", runId)
                .orderByAsc("round_number")));
        return result;
    }

    @Transactional
    public Map<String, Object> submitSupplement(
            String runId,
            Integer userId,
            Integer round,
            Map<String, String> answers) {
        if (round == null || round < 1 || round > 2 || answers == null
                || answers.isEmpty() || answers.size() > 4
                || !ALLOWED_SUPPLEMENT_FIELDS.containsAll(answers.keySet())) {
            throw new IllegalArgumentException("Invalid supplement payload");
        }
        for (String answer : answers.values()) {
            if (answer == null || answer.trim().isEmpty() || answer.length() > 500) {
                throw new IllegalArgumentException("Supplement answers must contain 1 to 500 characters");
            }
        }
        AgentRunRecord run = findRun(runId);
        AgentCaseRecord agentCase = findCaseForRun(run, userId);
        AgentSupplementRecord existing = supplementMapper.selectOne(new QueryWrapper<AgentSupplementRecord>()
                .eq("run_id", runId)
                .eq("round_number", round));
        if (existing != null) {
            if (Objects.equals(parseJson(existing.getAnswersJson()), answers)) {
                return runResponse(runId, run.getStatus(), true, round);
            }
            throw new IllegalStateException("Supplement round already submitted with different answers");
        }
        if (!"WAITING_FOR_INFO".equals(run.getStatus())) {
            throw new IllegalStateException("Run is not waiting for information");
        }

        AgentSupplementRecord supplement = new AgentSupplementRecord();
        supplement.setRunId(runId);
        supplement.setRoundNumber(round);
        supplement.setUserId(userId);
        supplement.setAnswersJson(writeJson(answers));
        supplementMapper.insert(supplement);
        run.setStatus("RUNNING");
        runMapper.updateById(run);
        agentCase.setStatus("RUNNING");
        caseMapper.updateById(agentCase);
        return runResponse(runId, "RUNNING", false, round);
    }

    @Transactional
    public Map<String, Object> submitReview(
            String runId,
            Integer reviewerId,
            String reviewerRole,
            String decision,
            String comment,
            Map<String, Object> edits) {
        if (!canReview(reviewerRole)) {
            throw new SecurityException("Reviewer role is not authorized");
        }
        if (!Arrays.asList("approve", "modify", "return").contains(decision)) {
            throw new IllegalArgumentException("Unsupported review decision");
        }
        String normalizedComment = comment == null ? "" : comment;
        Map<String, Object> normalizedEdits = edits == null ? Collections.<String, Object>emptyMap() : edits;
        validateReviewEdits(decision, normalizedComment, normalizedEdits);

        AgentRunRecord run = findRun(runId);
        AgentCaseRecord agentCase = findCaseForRun(run, null);
        AgentReviewRecord existing = reviewMapper.selectOne(new QueryWrapper<AgentReviewRecord>()
                .eq("run_id", runId));
        if (existing != null) {
            if (existing.getReviewerId().equals(reviewerId)
                    && existing.getDecision().equals(decision)
                    && existing.getComment().equals(normalizedComment)
                    && Objects.equals(parseJson(existing.getEditsJson()), normalizedEdits)) {
                return runResponse(runId, run.getStatus(), true, null);
            }
            throw new IllegalStateException("Run already has a different review record");
        }
        if (!"WAITING_FOR_REVIEW".equals(run.getStatus())) {
            throw new IllegalStateException("Run is not waiting for review");
        }
        if (reviewerId.equals(agentCase.getUserId())) {
            throw new SecurityException("Reviewer cannot review their own case");
        }

        AgentReviewRecord review = new AgentReviewRecord();
        review.setRunId(runId);
        review.setReviewerId(reviewerId);
        review.setDecision(decision);
        review.setComment(normalizedComment);
        review.setEditsJson(writeJson(normalizedEdits));
        reviewMapper.insert(review);

        run.setStatus("RUNNING");
        runMapper.updateById(run);
        agentCase.setStatus("RUNNING");
        caseMapper.updateById(agentCase);
        return runResponse(runId, "RUNNING", false, null);
    }

    @Transactional
    public String acceptEvent(String runId, AgentEventRequest request) {
        if (request.getEventSeq() == null || request.getEventSeq() <= 0
                || request.getEventType() == null
                || !ALLOWED_STATUSES.contains(request.getStatus())
                || request.getPayload() == null
                || request.getOccurredAt() == null) {
            throw new IllegalArgumentException("Invalid event");
        }

        AgentRunRecord run = runMapper.selectOne(new QueryWrapper<AgentRunRecord>()
                .eq("run_id", runId));
        if (run == null) {
            throw new NoSuchElementException("Run not found");
        }

        AgentEventRecord duplicate = eventMapper.selectOne(new QueryWrapper<AgentEventRecord>()
                .eq("run_id", runId)
                .eq("event_seq", request.getEventSeq()));
        if (duplicate != null || request.getEventSeq() <= run.getLastEventSeq()) {
            return "duplicate";
        }
        if (isTerminal(run.getStatus())) {
            throw new IllegalArgumentException("Run already terminal");
        }
        if (request.getEventSeq() != run.getLastEventSeq() + 1) {
            throw new IllegalArgumentException("Event sequence gap");
        }

        Date occurredAt;
        try {
            occurredAt = Date.from(OffsetDateTime.parse(request.getOccurredAt()).toInstant());
        } catch (RuntimeException exception) {
            throw new IllegalArgumentException("Invalid event timestamp");
        }
        AgentEventRecord event = new AgentEventRecord();
        event.setRunId(runId);
        event.setEventSeq(request.getEventSeq());
        event.setEventType(request.getEventType());
        event.setStatus(request.getStatus());
        event.setPayloadJson(writeJson(request.getPayload()));
        event.setOccurredAt(occurredAt);
        eventMapper.insert(event);

        run.setStatus(request.getStatus());
        run.setLastEventSeq(request.getEventSeq());
        if (isTerminal(request.getStatus())) {
            run.setFinishedAt(new Date());
        }
        Object draft = request.getPayload().get("draft");
        if (draft != null) {
            run.setResultJson(writeJson(draft));
        }
        Object errorCode = request.getPayload().get("errorCode");
        if (errorCode != null) {
            run.setErrorCode(String.valueOf(errorCode));
        }
        runMapper.updateById(run);

        AgentCaseRecord agentCase = caseMapper.selectById(run.getCaseId());
        if (agentCase != null) {
            agentCase.setStatus(request.getStatus());
            caseMapper.updateById(agentCase);
        }
        return "accepted";
    }

    @Transactional
    public void markDispatchFailed(String runId, String errorCode) {
        AgentRunRecord run = runMapper.selectOne(new QueryWrapper<AgentRunRecord>()
                .eq("run_id", runId));
        if (run == null || isTerminal(run.getStatus())) {
            return;
        }
        run.setStatus("FAILED");
        run.setErrorCode(errorCode);
        run.setFinishedAt(new Date());
        run.setLastEventSeq(run.getLastEventSeq() + 1);
        runMapper.updateById(run);

        AgentEventRecord event = new AgentEventRecord();
        event.setRunId(runId);
        event.setEventSeq(run.getLastEventSeq());
        event.setEventType("dispatch.failed");
        event.setStatus("FAILED");
        event.setPayloadJson(writeJson(Collections.singletonMap("errorCode", errorCode)));
        event.setOccurredAt(new Date());
        eventMapper.insert(event);

        AgentCaseRecord agentCase = caseMapper.selectById(run.getCaseId());
        if (agentCase != null) {
            agentCase.setStatus("FAILED");
            caseMapper.updateById(agentCase);
        }
    }

    private boolean isTerminal(String status) {
        return Arrays.asList("COMPLETED", "PARTIAL", "FAILED", "CANCELLED", "RETURNED").contains(status);
    }

    private boolean canReview(String role) {
        return RoleEnum.ROLE_ADMIN.name().equals(role) || RoleEnum.ROLE_MAINTENANCE.name().equals(role);
    }

    private AgentRunRecord findRun(String runId) {
        AgentRunRecord run = runMapper.selectOne(new QueryWrapper<AgentRunRecord>()
                .eq("run_id", runId));
        if (run == null) {
            throw new NoSuchElementException("Run not found");
        }
        return run;
    }

    private AgentCaseRecord findCaseForRun(AgentRunRecord run, Integer ownerId) {
        QueryWrapper<AgentCaseRecord> query = new QueryWrapper<AgentCaseRecord>()
                .eq("id", run.getCaseId());
        if (ownerId != null) {
            query.eq("user_id", ownerId);
        }
        AgentCaseRecord agentCase = caseMapper.selectOne(query);
        if (agentCase == null) {
            throw new SecurityException("Case access is not authorized");
        }
        return agentCase;
    }

    private void validateReviewEdits(String decision, String comment, Map<String, Object> edits) {
        if (comment.length() > 2000 || !ALLOWED_REVIEW_EDITS.containsAll(edits.keySet())) {
            throw new IllegalArgumentException("Invalid review comment or non-editable fields");
        }
        if ("modify".equals(decision) != !edits.isEmpty()) {
            throw new IllegalArgumentException("Modify requires allowed edits; other decisions do not accept edits");
        }
        for (Map.Entry<String, Object> entry : edits.entrySet()) {
            Object value = entry.getValue();
            if ("summary".equals(entry.getKey())) {
                if (!(value instanceof String) || ((String) value).length() > 2000) {
                    throw new IllegalArgumentException("Edited summary is invalid");
                }
            } else {
                if (!(value instanceof List) || ((List<?>) value).size() > 20) {
                    throw new IllegalArgumentException("Edited list field is invalid");
                }
                for (Object item : (List<?>) value) {
                    if (!(item instanceof String) || ((String) item).trim().isEmpty()
                            || ((String) item).length() > 500) {
                        throw new IllegalArgumentException("Edited list entry is invalid");
                    }
                }
            }
        }
    }

    private Map<String, Object> runResponse(String runId, String status, boolean idempotent, Integer round) {
        Map<String, Object> response = new LinkedHashMap<>();
        response.put("runId", runId);
        response.put("status", status);
        response.put("idempotent", idempotent);
        if (round != null) {
            response.put("round", round);
        }
        return response;
    }

    private String writeJson(Object value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (Exception exception) {
            throw new IllegalStateException("Failed to serialize Agent data", exception);
        }
    }

    private Object parseJson(String json) {
        if (json == null) {
            return null;
        }
        try {
            return objectMapper.readValue(json, new TypeReference<Object>() {});
        } catch (Exception exception) {
            return Collections.singletonMap("errorCode", "STORED_RESULT_INVALID");
        }
    }

    private String sha256(String content) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(content.getBytes(StandardCharsets.UTF_8));
            StringBuilder hex = new StringBuilder();
            for (byte value : digest) {
                hex.append(String.format("%02x", value));
            }
            return hex.toString();
        } catch (Exception exception) {
            throw new IllegalStateException("SHA-256 is unavailable", exception);
        }
    }
}
