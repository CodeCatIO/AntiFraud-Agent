package com.cucn.springboot.dto;

import lombok.Data;

import java.util.Map;

@Data
public class ReviewAgentRunRequest {

    private String decision;

    private String comment;

    private Map<String, Object> edits;
}
