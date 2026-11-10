package com.cucn.springboot.dto;

import lombok.Data;

import java.util.Map;

@Data
public class SupplementAgentRunRequest {

    private Integer round;

    private Map<String, String> answers;
}
