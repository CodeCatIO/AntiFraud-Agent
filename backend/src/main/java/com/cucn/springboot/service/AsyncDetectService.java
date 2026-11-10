package com.cucn.springboot.service;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.cucn.springboot.client.AiServiceClient;
import com.cucn.springboot.entity.DetectionRecord;
import com.cucn.springboot.mapper.DetectionRecordMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import javax.annotation.Resource;
import java.util.Date;
import java.util.Map;

/**
 * Async Detection Service
 * 异步检测服务
 *
 * Handles long-running AI detection tasks asynchronously.
 * When a detection task takes too long (e.g., large audio files, high-res images),
 * instead of blocking the HTTP request, we return a task ID immediately
 * and let the client poll for results later.
 *
 * 异步处理耗时较长的AI检测任务。
 * 当检测任务耗时较长时（如大音频文件、高分辨率图片），不阻塞HTTP请求，
 * 而是立即返回任务ID，让客户端稍后轮询结果。
 *
 * Why async?
 * - Better user experience: no long waiting, no request timeout
 * - Better server resource utilization: threads not blocked on I/O
 * - Scalability: can handle more concurrent requests
 *
 * 为什么用异步？
 * - 用户体验更好：不用长时间等待，不会请求超时
 * - 服务器资源利用率更高：线程不会在I/O上阻塞
 * - 可扩展性：能处理更多并发请求
 */
@Slf4j
@Service
public class AsyncDetectService {

    @Resource
    private AiServiceClient aiServiceClient;

    @Resource
    private DetectionRecordMapper detectionRecordMapper;

    /**
     * Asynchronously process voice detection.
     * 异步处理语音检测。
     *
     * @param recordId existing detection record ID (status will be updated)
     * @param file     audio file to analyze
     */
    @Async("aiDetectionExecutor")
    public void processVoiceAsync(Integer recordId, MultipartFile file) {
        log.info("Async voice detection started for recordId={}", recordId);
        try {
            Map<String, Object> result = aiServiceClient.detectVoice(file);
            updateRecordWithResult(recordId, result);
            log.info("Async voice detection completed for recordId={}", recordId);
        } catch (Exception e) {
            log.error("Async voice detection failed for recordId={}", recordId, e);
            updateRecordWithError(recordId, e.getMessage());
        }
    }

    /**
     * Asynchronously process image detection.
     * 异步处理图像检测。
     *
     * @param recordId existing detection record ID
     * @param file     image file to analyze
     */
    @Async("aiDetectionExecutor")
    public void processImageAsync(Integer recordId, MultipartFile file) {
        log.info("Async image detection started for recordId={}", recordId);
        try {
            Map<String, Object> result = aiServiceClient.detectImage(file);
            updateRecordWithResult(recordId, result);
            log.info("Async image detection completed for recordId={}", recordId);
        } catch (Exception e) {
            log.error("Async image detection failed for recordId={}", recordId, e);
            updateRecordWithError(recordId, e.getMessage());
        }
    }

    /**
     * Check the status of an async detection task.
     * 查询异步检测任务的状态。
     *
     * @param recordId detection record ID
     * @return detection record with current status and result
     */
    public DetectionRecord getTaskStatus(Integer recordId) {
        return detectionRecordMapper.selectById(recordId);
    }

    // ============================================================
    //  Private Helper Methods  私有辅助方法
    // ============================================================

    /**
     * Update the detection record with successful AI result.
     * 用AI检测成功结果更新检测记录。
     */
    private void updateRecordWithResult(Integer recordId, Map<String, Object> aiResult) {
        DetectionRecord record = new DetectionRecord();
        record.setId(recordId);

        Object scoreObj = aiResult.get("riskScore");
        if (scoreObj == null) scoreObj = aiResult.get("risk_score");
        int riskScore = 0;
        if (scoreObj instanceof Number) riskScore = ((Number) scoreObj).intValue();

        record.setRiskScore(riskScore);

        String riskLevel;
        if (riskScore >= 70) riskLevel = "高风险";
        else if (riskScore >= 40) riskLevel = "中风险";
        else riskLevel = "低风险";
        record.setRiskLevel(riskLevel);

        try {
            record.setDetail(new com.fasterxml.jackson.databind.ObjectMapper().writeValueAsString(aiResult));
        } catch (Exception e) {
            record.setDetail(aiResult.toString());
        }

        record.setStatus("completed");
        detectionRecordMapper.updateById(record);
    }

    /**
     * Update the detection record with error information.
     * 用错误信息更新检测记录。
     */
    private void updateRecordWithError(Integer recordId, String errorMsg) {
        DetectionRecord record = new DetectionRecord();
        record.setId(recordId);
        record.setRiskScore(0);
        record.setRiskLevel("检测失败");
        record.setDetail("{\"error\":\"" + errorMsg + "\"}");
        record.setStatus("failed");
        detectionRecordMapper.updateById(record);
    }
}
