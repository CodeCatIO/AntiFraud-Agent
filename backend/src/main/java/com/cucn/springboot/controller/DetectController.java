package com.cucn.springboot.controller;

import cn.hutool.core.util.StrUtil;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.cucn.springboot.client.AiServiceClient;
import com.cucn.springboot.common.Result;
import com.cucn.springboot.entity.DetectionRecord;
import com.cucn.springboot.entity.User;
import com.cucn.springboot.mapper.DetectionRecordMapper;
import com.cucn.springboot.utils.TokenUtils;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import javax.annotation.Resource;
import java.io.File;
import java.util.*;

/**
 * Core Detection Controller
 * 核心检测接口控制器
 *
 * Provides text/voice/image/composite anti-fraud detection capabilities.
 * Delegates actual AI analysis to the Python AI microservice via AiServiceClient
 * (HTTP REST API), replacing the old ProcessBuilder approach.
 *
 * 提供文本/语音/图像/综合反诈检测能力。
 * 通过 AiServiceClient（HTTP REST API）将实际AI分析委托给Python AI微服务，
 * 替代旧的 ProcessBuilder 方式。
 *
 * Architecture:
 *   Frontend → DetectController → AiServiceClient → Python Flask Microservice
 *                                    (HTTP)
 */
@Slf4j
@RestController
@RequestMapping("/detect")
public class DetectController {

    @Resource
    private DetectionRecordMapper detectionRecordMapper;

    @Resource
    private AiServiceClient aiServiceClient;

    // ============================================================
    //  Text Detection  文本检测
    // ============================================================

    /**
     * Text fraud detection endpoint.
     * 文本诈骗检测接口。
     *
     * @param params request body with "content" field
     * @return detection result with recordId, riskScore, riskLevel, detail
     */
    @PostMapping("/text")
    public Result detectText(@RequestBody Map<String, String> params) {
        String content = params.get("content");
        if (StrUtil.isBlank(content)) {
            return Result.error("400", "检测内容不能为空 Content cannot be empty");
        }
        User currentUser = TokenUtils.getCurrentUser();
        if (currentUser == null) {
            return Result.error("401", "请先登录 Please login first");
        }

        try {
            // Optional model selection (baseline / bilstm / cnn / ensemble)
            // 可选模型选择参数，为空时使用 AI 服务默认融合模型
            String model = params.get("model");

            // Call AI microservice via HTTP
            // 通过 HTTP 调用 AI 微服务
            Map<String, Object> aiResult = aiServiceClient.detectText(content, model);
            if (isAiError(aiResult)) {
                return Result.error("400", aiErrorMessage(aiResult));
            }

            int riskScore = getRiskScore(aiResult);
            String riskLevel = getRiskLevel(riskScore);

            // Save detection record
            // 保存检测记录
            DetectionRecord record = saveRecord(
                    currentUser.getId(),
                    "text",
                    content.length() > 200 ? content.substring(0, 200) : content,
                    riskScore,
                    riskLevel,
                    aiResult
            );

            // Build response
            Map<String, Object> data = buildResponse(record, aiResult);
            return Result.success(data);

        } catch (Exception e) {
            log.error("Text detection failed", e);
            return Result.error("500", "文本检测失败 Text detection failed: " + e.getMessage());
        }
    }

    // ============================================================
    //  Voice Detection  语音检测
    // ============================================================

    /**
     * Voice fraud detection endpoint.
     * 语音诈骗检测接口。
     *
     * @param file uploaded audio file
     * @return detection result
     */
    @PostMapping("/voice")
    public Result detectVoice(@RequestParam MultipartFile file,
                              @RequestParam(required = false) String model) {
        if (file.isEmpty()) {
            return Result.error("400", "请上传语音文件 Please upload a voice file");
        }
        User currentUser = TokenUtils.getCurrentUser();
        if (currentUser == null) {
            return Result.error("401", "请先登录 Please login first");
        }

        try {
            String originalFilename = file.getOriginalFilename();

            // Call AI microservice (model: gmm / svm / rf, null = default)
            // 调用 AI 微服务，model 为空时使用默认（最佳）模型
            Map<String, Object> aiResult = aiServiceClient.detectVoice(file, model);
            if (isAiError(aiResult)) {
                return Result.error("400", aiErrorMessage(aiResult));
            }

            int riskScore = getRiskScore(aiResult);
            String riskLevel = getRiskLevel(riskScore);

            DetectionRecord record = saveRecord(
                    currentUser.getId(),
                    "voice",
                    "语音文件：" + originalFilename,
                    riskScore,
                    riskLevel,
                    aiResult
            );

            Map<String, Object> data = buildResponse(record, aiResult);
            return Result.success(data);

        } catch (Exception e) {
            log.error("Voice detection failed", e);
            return Result.error("500", "语音检测失败 Voice detection failed: " + e.getMessage());
        }
    }

    // ============================================================
    //  Image Detection  图像检测
    // ============================================================

    /**
     * Image fraud detection endpoint.
     * 图像诈骗检测接口。
     *
     * @param file uploaded image file
     * @return detection result
     */
    @PostMapping("/image")
    public Result detectImage(@RequestParam MultipartFile file,
                              @RequestParam(required = false) String model) {
        if (file.isEmpty()) {
            return Result.error("400", "请上传图像文件 Please upload an image file");
        }
        User currentUser = TokenUtils.getCurrentUser();
        if (currentUser == null) {
            return Result.error("401", "请先登录 Please login first");
        }

        try {
            String originalFilename = file.getOriginalFilename();

            // Call AI microservice (model: logistic_regression / random_forest / svm, null = default)
            // 调用 AI 微服务，model 为空时使用默认（最佳）模型
            Map<String, Object> aiResult = aiServiceClient.detectImage(file, model);
            if (isAiError(aiResult)) {
                return Result.error("400", aiErrorMessage(aiResult));
            }

            int riskScore = getRiskScore(aiResult);
            String riskLevel = getRiskLevel(riskScore);

            DetectionRecord record = saveRecord(
                    currentUser.getId(),
                    "image",
                    "图像文件：" + originalFilename,
                    riskScore,
                    riskLevel,
                    aiResult
            );

            Map<String, Object> data = buildResponse(record, aiResult);
            return Result.success(data);

        } catch (Exception e) {
            log.error("Image detection failed", e);
            return Result.error("500", "图像检测失败 Image detection failed: " + e.getMessage());
        }
    }

    // ============================================================
    //  Composite Risk Assessment  综合风险评估
    // ============================================================

    /**
     * Composite fraud risk assessment endpoint.
     * 综合诈骗风险评估接口。
     *
     * @param params request body with textScore, voiceScore, imageScore
     * @return composite assessment result
     */
    @PostMapping("/composite")
    public Result detectComposite(@RequestBody Map<String, Integer> params) {
        Integer textScore = params.get("textScore");
        Integer voiceScore = params.get("voiceScore");
        Integer imageScore = params.get("imageScore");

        if (textScore == null || voiceScore == null || imageScore == null) {
            return Result.error("400", "请提供完整的文本、语音、图像风险分数 Please provide all three scores");
        }

        User currentUser = TokenUtils.getCurrentUser();
        if (currentUser == null) {
            return Result.error("401", "请先登录 Please login first");
        }

        try {
            // Call AI microservice
            Map<String, Object> aiResult = aiServiceClient.assessRisk(textScore, voiceScore, imageScore);

            int riskScore = getRiskScore(aiResult);
            String riskLevel = getRiskLevel(riskScore);

            String inputSummary = "综合评估-文本:" + textScore + " 语音:" + voiceScore + " 图像:" + imageScore;
            DetectionRecord record = saveRecord(
                    currentUser.getId(),
                    "composite",
                    inputSummary,
                    riskScore,
                    riskLevel,
                    aiResult
            );

            Map<String, Object> data = buildResponse(record, aiResult);
            return Result.success(data);

        } catch (Exception e) {
            log.error("Composite risk assessment failed", e);
            return Result.error("500", "综合风险评估失败 Composite assessment failed: " + e.getMessage());
        }
    }

    // ============================================================
    //  Detection Records  检测记录
    // ============================================================

    /**
     * Get paginated detection records for current user.
     * 获取当前用户的分页检测记录。
     */
    @GetMapping("/records")
    public Result getRecords(
            @RequestParam(defaultValue = "1") Integer pageNum,
            @RequestParam(defaultValue = "10") Integer pageSize,
            @RequestParam(required = false) String type) {
        User currentUser = TokenUtils.getCurrentUser();
        if (currentUser == null) return Result.error("401", "请先登录 Please login first");

        Page<DetectionRecord> page = new Page<>(pageNum, pageSize);
        QueryWrapper<DetectionRecord> queryWrapper = new QueryWrapper<>();
        queryWrapper.eq("user_id", currentUser.getId());
        if (StrUtil.isNotBlank(type)) queryWrapper.eq("type", type);
        queryWrapper.orderByDesc("create_time");
        Page<DetectionRecord> resultPage = detectionRecordMapper.selectPage(page, queryWrapper);
        return Result.success(resultPage);
    }

    /**
     * Get detection statistics for current user.
     * 获取当前用户的检测统计数据。
     */
    @GetMapping("/stats")
    public Result getStats() {
        User currentUser = TokenUtils.getCurrentUser();
        if (currentUser == null) return Result.error("401", "请先登录 Please login first");

        Map<String, Object> stats = new HashMap<>();

        // Total count
        QueryWrapper<DetectionRecord> totalWrapper = new QueryWrapper<>();
        totalWrapper.eq("user_id", currentUser.getId());
        Long totalCount = detectionRecordMapper.selectCount(totalWrapper);
        stats.put("totalCount", totalCount);

        // Count by type
        Map<String, Long> typeCount = new HashMap<>();
        for (String t : Arrays.asList("text", "voice", "image", "composite")) {
            QueryWrapper<DetectionRecord> typeWrapper = new QueryWrapper<>();
            typeWrapper.eq("user_id", currentUser.getId()).eq("type", t);
            typeCount.put(t, detectionRecordMapper.selectCount(typeWrapper));
        }
        stats.put("typeCount", typeCount);

        // Count by risk level
        Map<String, Long> riskCount = new HashMap<>();
        for (String level : Arrays.asList("低风险", "中风险", "高风险")) {
            QueryWrapper<DetectionRecord> riskWrapper = new QueryWrapper<>();
            riskWrapper.eq("user_id", currentUser.getId()).eq("risk_level", level);
            riskCount.put(level, detectionRecordMapper.selectCount(riskWrapper));
        }
        stats.put("riskCount", riskCount);

        return Result.success(stats);
    }

    // ============================================================
    //  Private Helper Methods  私有辅助方法
    // ============================================================

    /**
     * Whether the AI service result represents a client error
     * (e.g. invalid model name) that must not be persisted.
     * 判断 AI 结果是否为客户端错误（如模型名非法），此类结果不入库。
     */
    private boolean isAiError(Map<String, Object> result) {
        return result != null && Boolean.TRUE.equals(result.get("error"));
    }

    /**
     * Extract a human-readable message from an AI service error result.
     * 从 AI 错误结果中提取可读提示。
     */
    private String aiErrorMessage(Map<String, Object> result) {
        Object detail = result.get("detail");
        if (StrUtil.isNotBlank(Objects.toString(detail, null))) {
            return String.valueOf(detail);
        }
        return "模型参数无效或检测服务返回错误 Invalid model or AI service error";
    }

    /**
     * Extract risk score from AI service result.
     * Supports both camelCase (riskScore) and snake_case (risk_score).
     * 从AI服务结果中提取风险分数。
     * 同时支持驼峰命名（riskScore）和下划线命名（risk_score）。
     */
    private int getRiskScore(Map<String, Object> result) {
        if (result == null) return 0;
        Object score = result.get("riskScore");
        if (score == null) score = result.get("risk_score");
        if (score instanceof Number) return ((Number) score).intValue();
        if (score instanceof String) {
            try { return Integer.parseInt((String) score); } catch (Exception ignored) {}
        }
        return 0;
    }

    /**
     * Determine risk level based on score.
     * 根据分数确定风险等级。
     */
    private String getRiskLevel(int riskScore) {
        if (riskScore >= 70) return "高风险";
        else if (riskScore >= 40) return "中风险";
        else return "低风险";
    }

    /**
     * Save a detection record to database.
     * 将检测记录保存到数据库。
     */
    private DetectionRecord saveRecord(Integer userId, String type, String inputContent,
                                       int riskScore, String riskLevel,
                                       Map<String, Object> aiResult) {
        DetectionRecord record = new DetectionRecord();
        record.setUserId(userId);
        record.setType(type);
        record.setInputContent(inputContent);
        record.setRiskScore(riskScore);
        record.setRiskLevel(riskLevel);
        try {
            record.setDetail(new com.fasterxml.jackson.databind.ObjectMapper().writeValueAsString(aiResult));
        } catch (Exception e) {
            record.setDetail(aiResult.toString());
        }
        record.setStatus("completed");
        record.setCreateTime(new Date());
        detectionRecordMapper.insert(record);
        return record;
    }

    /**
     * Build the API response data map.
     * 构建API响应数据Map。
     */
    private Map<String, Object> buildResponse(DetectionRecord record, Map<String, Object> aiResult) {
        Map<String, Object> data = new HashMap<>();
        data.put("recordId", record.getId());
        data.put("riskScore", record.getRiskScore());
        data.put("riskLevel", record.getRiskLevel());
        data.put("detail", aiResult);
        return data;
    }
}
