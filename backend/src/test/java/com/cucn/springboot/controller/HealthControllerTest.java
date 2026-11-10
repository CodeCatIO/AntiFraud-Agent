package com.cucn.springboot.controller;

import com.cucn.springboot.common.Result;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * Integration tests for HealthController
 * 健康检查控制器集成测试
 *
 * Uses MockMvc to test HTTP endpoints without starting a full server.
 * 使用 MockMvc 测试HTTP接口，无需启动完整服务器。
 */
@SpringBootTest
@AutoConfigureMockMvc
@DisplayName("HealthController Integration Tests - 健康检查集成测试")
class HealthControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    @DisplayName("Health endpoint returns 200 - 健康检查接口返回200")
    void testHealthEndpoint() throws Exception {
        mockMvc.perform(get("/health"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value("200"))
                .andExpect(jsonPath("$.data.status").exists())
                .andExpect(jsonPath("$.data.components.backend").value("ok"));
    }

    @Test
    @DisplayName("Liveness endpoint - 存活探测")
    void testLivenessEndpoint() throws Exception {
        mockMvc.perform(get("/health/liveness"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value("200"))
                .andExpect(jsonPath("$.data").value("alive"));
    }

    @Test
    @DisplayName("Health response contains all components - 健康响应包含所有组件")
    void testHealthComponents() throws Exception {
        String response = mockMvc.perform(get("/health"))
                .andReturn()
                .getResponse()
                .getContentAsString();

        assertTrue(response.contains("backend"), "Should contain backend status");
        assertTrue(response.contains("database"), "Should contain database status");
        assertTrue(response.contains("redis"), "Should contain redis status");
        assertTrue(response.contains("aiService"), "Should contain AI service status");
    }
}
