package com.cucn.springboot.dto;

import lombok.Data;

import java.util.Map;

@Data
public class AgentEventRequest {

    private Integer eventSeq;

    private String eventType;

    private String status;

    private Map<String, Object> payload;

    private String occurredAt;
}
