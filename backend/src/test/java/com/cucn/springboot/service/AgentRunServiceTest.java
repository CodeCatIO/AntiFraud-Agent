package com.cucn.springboot.service;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
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
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class AgentRunServiceTest {

    private final AgentCaseMapper caseMapper = mock(AgentCaseMapper.class);
    private final AgentRunMapper runMapper = mock(AgentRunMapper.class);
    private final AgentEventMapper eventMapper = mock(AgentEventMapper.class);
    private final AgentReviewMapper reviewMapper = mock(AgentReviewMapper.class);
    private final AgentSupplementMapper supplementMapper = mock(AgentSupplementMapper.class);
    private final AgentRunService service = new AgentRunService();

    @BeforeEach
    void setUp() {
        ReflectionTestUtils.setField(service, "caseMapper", caseMapper);
        ReflectionTestUtils.setField(service, "runMapper", runMapper);
        ReflectionTestUtils.setField(service, "eventMapper", eventMapper);
        ReflectionTestUtils.setField(service, "reviewMapper", reviewMapper);
        ReflectionTestUtils.setField(service, "supplementMapper", supplementMapper);
        ReflectionTestUtils.setField(service, "objectMapper", new ObjectMapper());
    }

    @Test
    void duplicateEventDoesNotRewriteTerminalRun() {
        AgentRunRecord run = runRecord("COMPLETED", 3);
        AgentEventRecord duplicate = new AgentEventRecord();
        duplicate.setRunId(run.getRunId());
        duplicate.setEventSeq(2);
        when(runMapper.selectOne(any(QueryWrapper.class))).thenReturn(run);
        when(eventMapper.selectOne(any(QueryWrapper.class))).thenReturn(duplicate);

        String result = service.acceptEvent(run.getRunId(), eventRequest(2, "RUNNING"));

        assertEquals("duplicate", result);
        verify(eventMapper, never()).insert(any(AgentEventRecord.class));
        verify(runMapper, never()).updateById(any(AgentRunRecord.class));
    }

    @Test
    void terminalRunRejectsLaterStatusRegression() {
        AgentRunRecord run = runRecord("COMPLETED", 3);
        when(runMapper.selectOne(any(QueryWrapper.class))).thenReturn(run);
        when(eventMapper.selectOne(any(QueryWrapper.class))).thenReturn(null);

        IllegalArgumentException error = assertThrows(
                IllegalArgumentException.class,
                () -> service.acceptEvent(run.getRunId(), eventRequest(4, "RUNNING"))
        );

        assertEquals("Run already terminal", error.getMessage());
        verify(eventMapper, never()).insert(any(AgentEventRecord.class));
        verify(runMapper, never()).updateById(any(AgentRunRecord.class));
    }

    @Test
    void rejectsSequenceGap() {
        AgentRunRecord run = runRecord("RUNNING", 1);
        when(runMapper.selectOne(any(QueryWrapper.class))).thenReturn(run);
        when(eventMapper.selectOne(any(QueryWrapper.class))).thenReturn(null);

        IllegalArgumentException error = assertThrows(
                IllegalArgumentException.class,
                () -> service.acceptEvent(run.getRunId(), eventRequest(3, "RUNNING"))
        );

        assertEquals("Event sequence gap", error.getMessage());
        verify(eventMapper, never()).insert(any(AgentEventRecord.class));
    }

    @Test
    void acceptsNextSequenceAndPersistsDraft() {
        AgentRunRecord run = runRecord("RUNNING", 1);
        AgentCaseRecord agentCase = new AgentCaseRecord();
        agentCase.setId(run.getCaseId());
        when(runMapper.selectOne(any(QueryWrapper.class))).thenReturn(run);
        when(eventMapper.selectOne(any(QueryWrapper.class))).thenReturn(null);
        when(caseMapper.selectById(run.getCaseId())).thenReturn(agentCase);

        String result = service.acceptEvent(
                run.getRunId(),
                eventRequest(2, "COMPLETED")
        );

        assertEquals("accepted", result);
        assertEquals(2, run.getLastEventSeq());
        assertEquals("COMPLETED", run.getStatus());
        verify(eventMapper).insert(any(AgentEventRecord.class));
        verify(runMapper).updateById(run);
        verify(caseMapper).updateById(agentCase);
    }

    @Test
    void workerCannotSubmitReview() {
        assertThrows(
                SecurityException.class,
                () -> service.submitReview(
                        "11111111-1111-1111-1111-111111111111",
                        7,
                        "ROLE_WORKER",
                        "approve",
                        "",
                        Collections.<String, Object>emptyMap()
                )
        );
        verify(runMapper, never()).selectOne(any(QueryWrapper.class));
    }

    @Test
    void reviewerCanReadAnotherOwnersRunButWorkerCannot() {
        AgentRunRecord run = runRecord("WAITING_FOR_REVIEW", 3);
        AgentCaseRecord agentCase = new AgentCaseRecord();
        agentCase.setId(run.getCaseId());
        agentCase.setUserId(99);
        when(runMapper.selectOne(any(QueryWrapper.class))).thenReturn(run);
        when(caseMapper.selectOne(any(QueryWrapper.class))).thenReturn(agentCase);
        when(eventMapper.selectList(any(QueryWrapper.class))).thenReturn(Collections.emptyList());
        when(reviewMapper.selectList(any(QueryWrapper.class))).thenReturn(Collections.emptyList());
        when(supplementMapper.selectList(any(QueryWrapper.class))).thenReturn(Collections.emptyList());

        Map<String, Object> reviewerView = service.getRunForUser(run.getRunId(), 7, "ROLE_ADMIN");

        assertNotNull(reviewerView);
        assertEquals(run.getRunId(), reviewerView.get("runId"));
        assertNull(service.getRunForUser(run.getRunId(), 7, "ROLE_WORKER"));
    }

    @Test
    void reviewCannotEditDetectorEvidenceOrCitations() {
        Map<String, Object> edits = new LinkedHashMap<>();
        edits.put("detection", Collections.singletonMap("riskScore", 100));

        IllegalArgumentException error = assertThrows(
                IllegalArgumentException.class,
                () -> service.submitReview(
                        "11111111-1111-1111-1111-111111111111",
                        7,
                        "ROLE_ADMIN",
                        "modify",
                        "",
                        edits
                )
        );

        assertEquals("Invalid review comment or non-editable fields", error.getMessage());
        verify(runMapper, never()).selectOne(any(QueryWrapper.class));
    }

    @Test
    void adminReviewIsAuditedAndMovesRunToRunning() {
        AgentRunRecord run = runRecord("WAITING_FOR_REVIEW", 3);
        AgentCaseRecord agentCase = new AgentCaseRecord();
        agentCase.setId(run.getCaseId());
        agentCase.setUserId(99);
        when(runMapper.selectOne(any(QueryWrapper.class))).thenReturn(run);
        when(caseMapper.selectOne(any(QueryWrapper.class))).thenReturn(agentCase);
        when(reviewMapper.selectOne(any(QueryWrapper.class))).thenReturn(null);
        Map<String, Object> edits = Collections.<String, Object>singletonMap("summary", "复核后摘要");

        Map<String, Object> response = service.submitReview(
                run.getRunId(),
                7,
                "ROLE_ADMIN",
                "modify",
                "补充审核说明",
                edits
        );

        assertEquals(false, response.get("idempotent"));
        assertEquals("RUNNING", run.getStatus());
        assertEquals("RUNNING", agentCase.getStatus());
        verify(reviewMapper).insert(any(AgentReviewRecord.class));
        verify(runMapper).updateById(run);
        verify(caseMapper).updateById(agentCase);
    }

    @Test
    void supplementRequiresCaseOwnerAndWaitingState() {
        AgentRunRecord run = runRecord("WAITING_FOR_INFO", 2);
        when(runMapper.selectOne(any(QueryWrapper.class))).thenReturn(run);
        when(caseMapper.selectOne(any(QueryWrapper.class))).thenReturn(null);
        Map<String, String> answers = Collections.singletonMap("contact_channel", "微信");

        assertThrows(
                SecurityException.class,
                () -> service.submitSupplement(run.getRunId(), 7, 1, answers)
        );
        verify(supplementMapper, never()).insert(any(AgentSupplementRecord.class));
    }

    @Test
    void ownerSupplementIsStoredAndRunResumes() {
        AgentRunRecord run = runRecord("WAITING_FOR_INFO", 2);
        AgentCaseRecord agentCase = new AgentCaseRecord();
        agentCase.setId(run.getCaseId());
        agentCase.setUserId(7);
        when(runMapper.selectOne(any(QueryWrapper.class))).thenReturn(run);
        when(caseMapper.selectOne(any(QueryWrapper.class))).thenReturn(agentCase);
        when(supplementMapper.selectOne(any(QueryWrapper.class))).thenReturn(null);
        Map<String, String> answers = Collections.singletonMap("contact_channel", "微信");

        Map<String, Object> response = service.submitSupplement(run.getRunId(), 7, 1, answers);

        assertEquals(false, response.get("idempotent"));
        assertEquals("RUNNING", run.getStatus());
        verify(supplementMapper).insert(any(AgentSupplementRecord.class));
        verify(runMapper).updateById(run);
        verify(caseMapper).updateById(agentCase);
    }

    private AgentRunRecord runRecord(String status, int lastEventSeq) {
        AgentRunRecord run = new AgentRunRecord();
        run.setId(10L);
        run.setRunId("11111111-1111-1111-1111-111111111111");
        run.setCaseId(20L);
        run.setStatus(status);
        run.setLastEventSeq(lastEventSeq);
        return run;
    }

    private AgentEventRequest eventRequest(int eventSeq, String status) {
        AgentEventRequest request = new AgentEventRequest();
        request.setEventSeq(eventSeq);
        request.setEventType("run.progress");
        request.setStatus(status);
        request.setPayload(Collections.<String, Object>singletonMap(
                "draft",
                Collections.<String, Object>singletonMap("summary", "合成结果")
        ));
        request.setOccurredAt("2026-10-26T01:00:00Z");
        return request;
    }
}
