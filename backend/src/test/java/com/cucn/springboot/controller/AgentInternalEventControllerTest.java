package com.cucn.springboot.controller;

import com.cucn.springboot.common.Result;
import com.cucn.springboot.dto.AgentEventRequest;
import com.cucn.springboot.service.AgentRunService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.Collections;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class AgentInternalEventControllerTest {

    private final AgentRunService agentRunService = mock(AgentRunService.class);
    private final AgentInternalEventController controller = new AgentInternalEventController();

    @BeforeEach
    void setUp() {
        ReflectionTestUtils.setField(controller, "sharedSecret", "test-agent-secret");
        ReflectionTestUtils.setField(controller, "agentRunService", agentRunService);
    }

    @Test
    void rejectsInvalidServiceToken() {
        ResponseEntity<Result> response = controller.receiveEvent(
                "run-id",
                "wrong-secret",
                validRequest()
        );

        assertEquals(HttpStatus.UNAUTHORIZED, response.getStatusCode());
        verify(agentRunService, never()).acceptEvent("run-id", validRequest());
    }

    @Test
    void acceptsAuthorizedEvent() {
        AgentEventRequest request = validRequest();
        when(agentRunService.acceptEvent("run-id", request)).thenReturn("accepted");

        ResponseEntity<Result> response = controller.receiveEvent(
                "run-id",
                "test-agent-secret",
                request
        );

        assertEquals(HttpStatus.OK, response.getStatusCode());
        assertEquals("200", response.getBody().getCode());
        assertEquals(
                "accepted",
                ((java.util.Map<?, ?>) response.getBody().getData()).get("outcome")
        );
        verify(agentRunService).acceptEvent("run-id", request);
    }

    private AgentEventRequest validRequest() {
        AgentEventRequest request = new AgentEventRequest();
        request.setEventSeq(1);
        request.setEventType("run.started");
        request.setStatus("RUNNING");
        request.setPayload(Collections.<String, Object>emptyMap());
        request.setOccurredAt("2026-10-26T01:00:00Z");
        return request;
    }
}
