package com.cucn.springboot.controller;

import com.cucn.springboot.client.AiServiceClient;
import com.cucn.springboot.common.Result;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import javax.annotation.Resource;
import javax.sql.DataSource;
import java.sql.Connection;
import java.util.HashMap;
import java.util.Map;

/**
 * System Health Check Controller
 * 系统健康检查控制器
 *
 * Provides health check endpoints for monitoring and DevOps purposes.
 * Reports the status of all system components: backend, database, Redis, AI service.
 *
 * 提供健康检查接口，用于监控和运维目的。
 * 报告所有系统组件的状态：后端、数据库、Redis、AI服务。
 *
 * This is useful for:
 * - Docker/Kubernetes health probes
 * - Monitoring dashboards
 * - Quick debugging of system issues
 *
 * 用途：
 * - Docker/Kubernetes 健康探测
 * - 监控仪表盘
 * - 快速定位系统问题
 */
@Slf4j
@RestController
@RequestMapping("/health")
public class HealthController {

    @Resource
    private DataSource dataSource;

    @Resource
    private RedisTemplate<String, Object> redisTemplate;

    @Resource
    private AiServiceClient aiServiceClient;

    /**
     * Full system health check.
     * 完整的系统健康检查。
     *
     * Checks all downstream services and returns their status.
     * 检查所有下游服务并返回它们的状态。
     *
     * Response:
     *   {
     *     "status": "ok" | "degraded" | "down",
     *     "components": {
     *       "backend": "ok",
     *       "database": "ok",
     *       "redis": "ok",
     *       "aiService": "ok"
     *     }
     *   }
     */
    @GetMapping
    public Result healthCheck() {
        Map<String, Object> components = new HashMap<>();
        int healthyCount = 0;
        int totalCount = 4;

        // 1. Backend (this service is running, so always ok)
        // 1. 后端（这个服务在运行，所以一定是ok的）
        components.put("backend", "ok");
        healthyCount++;

        // 2. Database check
        // 2. 数据库检查
        try (Connection conn = dataSource.getConnection()) {
            if (conn.isValid(2)) {
                components.put("database", "ok");
                healthyCount++;
            } else {
                components.put("database", "degraded");
            }
        } catch (Exception e) {
            log.warn("Database health check failed: {}", e.getMessage());
            components.put("database", "down");
        }

        // 3. Redis check
        // 3. Redis 检查
        try {
            String pong = redisTemplate.getConnectionFactory()
                    .getConnection().ping();
            if ("PONG".equals(pong)) {
                components.put("redis", "ok");
                healthyCount++;
            } else {
                components.put("redis", "degraded");
            }
        } catch (Exception e) {
            log.warn("Redis health check failed: {}", e.getMessage());
            components.put("redis", "down");
        }

        // 4. AI service check
        // 4. AI 服务检查
        try {
            boolean aiHealthy = aiServiceClient.isHealthy();
            if (aiHealthy) {
                components.put("aiService", "ok");
                healthyCount++;
            } else {
                components.put("aiService", "degraded");
            }
        } catch (Exception e) {
            log.warn("AI service health check failed: {}", e.getMessage());
            components.put("aiService", "down");
        }

        // Determine overall status
        // 确定整体状态
        String overallStatus;
        if (healthyCount == totalCount) {
            overallStatus = "ok";
        } else if (healthyCount >= 2) {
            overallStatus = "degraded";
        } else {
            overallStatus = "down";
        }

        Map<String, Object> result = new HashMap<>();
        result.put("status", overallStatus);
        result.put("healthyCount", healthyCount);
        result.put("totalCount", totalCount);
        result.put("components", components);

        return Result.success(result);
    }

    /**
     * Simple liveness probe - just confirms the app is running.
     * 简单的存活探测 - 仅确认应用在运行。
     *
     * Used by Kubernetes liveness probe.
     * 用于 Kubernetes 存活探测。
     */
    @GetMapping("/liveness")
    public Result liveness() {
        return Result.success("alive");
    }

    /**
     * Readiness probe - confirms the app is ready to serve traffic.
     * 就绪探测 - 确认应用已准备好接收流量。
     *
     * Checks database and Redis connectivity.
     * Used by Kubernetes readiness probe.
     * 检查数据库和Redis连接。用于 Kubernetes 就绪探测。
     */
    @GetMapping("/readiness")
    public Result readiness() {
        boolean dbOk = false;
        boolean redisOk = false;

        try (Connection conn = dataSource.getConnection()) {
            dbOk = conn.isValid(2);
        } catch (Exception ignored) {}

        try {
            redisTemplate.getConnectionFactory().getConnection().ping();
            redisOk = true;
        } catch (Exception ignored) {}

        if (dbOk && redisOk) {
            return Result.success("ready");
        } else {
            return Result.error("503", "not ready - db:" + dbOk + " redis:" + redisOk);
        }
    }
}
