package com.cucn.springboot.client;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.stereotype.Component;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.util.StringUtils;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.multipart.MultipartFile;

import javax.annotation.Resource;
import java.util.HashMap;
import java.util.Map;

/**
 * AI Detection Service Client
 *
 * Communicates with the Python Flask AI detection microservice via HTTP REST API.
 * This replaces the old ProcessBuilder/Runtime.exec() approach for better
 * performance, stability, and scalability.
 *
 * 通过 HTTP REST API 与 Python Flask AI检测微服务通信。
 * 替代旧的 ProcessBuilder/Runtime.exec() 方式，提升性能、稳定性和可扩展性。
 *
 * Architecture:
 *   Java Backend ──HTTP REST──► Python Flask Microservice
 *   (AiServiceClient)            (text/voice/image detection)
 */
@Slf4j
@Component
public class AiServiceClient {

    @Value("${files.ai-service.base-url}")
    private String baseUrl;

    @Resource
    @Qualifier("aiServiceRestTemplate")
    private RestTemplate restTemplate;

    private final ObjectMapper objectMapper = new ObjectMapper();

    // ============================================================
    //  Health Check  健康检查
    // ============================================================

    /**
     * Check if the AI service is healthy and reachable.
     * 检查AI服务是否健康且可达。
     *
     * @return true if service responds with status ok
     */
    public boolean isHealthy() {
        try {
            String url = baseUrl + "/api/health";
            ResponseEntity<Map> response = restTemplate.getForEntity(url, Map.class);
            if (response.getStatusCode() == HttpStatus.OK && response.getBody() != null) {
                return "ok".equals(response.getBody().get("status"));
            }
            return false;
        } catch (RestClientException e) {
            log.warn("AI service health check failed: {}", e.getMessage());
            return false;
        }
    }

    // ============================================================
    //  Dataset Labels  数据集标签分布
    // ============================================================

    /**
     * 获取数据集标签统计（由 generate_dataset_labels.py 离线生成）。
     *
     * @return 标签 JSON；文件未生成或服务不可用时返回 null
     */
    public Map<String, Object> getDatasetLabels() {
        try {
            String url = baseUrl + "/api/dataset/labels";
            ResponseEntity<Map> response = restTemplate.getForEntity(url, Map.class);
            if (response.getStatusCode() != HttpStatus.OK || response.getBody() == null) {
                return null;
            }
            Map<String, Object> body = new HashMap<>(response.getBody());
            if (body.containsKey("error")) {
                log.warn("Dataset labels unavailable: {}", body.get("detail"));
                return null;
            }
            return body;
        } catch (Exception e) {
            log.warn("Dataset labels API call failed: {}", e.getMessage());
            return null;
        }
    }

    // ============================================================
    //  Text Detection  文本检测
    // ============================================================

    /**
     * Call text fraud detection API (default model selection).
     * 调用文本诈骗检测API（使用默认/融合模型）。
     *
     * @param content text content to analyze
     * @return detection result map with riskScore, riskLevel, detail, keywords, patterns
     */
    public Map<String, Object> detectText(String content) {
        return detectText(content, null);
    }

    /**
     * Call text fraud detection API with an explicit model.
     * 调用文本诈骗检测API，并指定模型（baseline / bilstm / cnn / ensemble）。
     *
     * @param content text content to analyze
     * @param model   model name, null/blank means server default (ensemble)
     * @return detection result map
     */
    public Map<String, Object> detectText(String content, String model) {
        try {
            String url = baseUrl + "/api/detect/text";
            Map<String, String> body = new HashMap<>();
            body.put("content", content);
            if (StringUtils.hasText(model)) {
                body.put("model", model.trim());
            }

            ResponseEntity<Map> response = postJson(url, body, Map.class);
            return handleResponse(response);
        } catch (HttpClientErrorException e) {
            // Flask 对非法/缺失模型返回 400，解析其错误体透传给上层
            return handleClientError(e, "Text detection service error 文本检测服务返回错误");
        } catch (Exception e) {
            log.error("Text detection API call failed", e);
            return buildFallbackResult("Text detection service unavailable 文本检测服务不可用");
        }
    }

    // ============================================================
    //  Voice Detection  语音检测
    // ============================================================

    /**
     * Call voice fraud detection API (default/best model).
     * 调用语音诈骗检测API（默认/最佳模型）。
     *
     * @param file voice audio file
     * @return detection result map with riskScore, riskLevel, detail, features
     */
    public Map<String, Object> detectVoice(MultipartFile file) {
        return detectVoice(file, null);
    }

    /**
     * Call voice fraud detection API with an explicit model.
     * 调用语音诈骗检测API，并指定模型（gmm / svm / rf）。
     *
     * @param file  voice audio file
     * @param model model name, null/blank means server default
     * @return detection result map
     */
    public Map<String, Object> detectVoice(MultipartFile file, String model) {
        try {
            String url = baseUrl + "/api/detect/voice";
            ResponseEntity<Map> response = postFile(url, file, model, Map.class);
            return handleResponse(response);
        } catch (HttpClientErrorException e) {
            return handleClientError(e, "Voice detection service error 语音检测服务返回错误");
        } catch (Exception e) {
            log.error("Voice detection API call failed", e);
            return buildFallbackResult("Voice detection service unavailable 语音检测服务不可用");
        }
    }

    // ============================================================
    //  Image Detection  图像检测
    // ============================================================

    /**
     * Call image fraud detection API (default/best model).
     * 调用图像诈骗检测API（默认/最佳模型）。
     *
     * @param file image file
     * @return detection result map with riskScore, riskLevel, detail, faceDetected, elaScore
     */
    public Map<String, Object> detectImage(MultipartFile file) {
        return detectImage(file, null);
    }

    /**
     * Call image fraud detection API with an explicit model.
     * 调用图像诈骗检测API，并指定模型（logistic_regression / random_forest / svm）。
     *
     * @param file  image file
     * @param model model name, null/blank means server default
     * @return detection result map
     */
    public Map<String, Object> detectImage(MultipartFile file, String model) {
        try {
            String url = baseUrl + "/api/detect/image";
            ResponseEntity<Map> response = postFile(url, file, model, Map.class);
            return handleResponse(response);
        } catch (HttpClientErrorException e) {
            return handleClientError(e, "Image detection service error 图像检测服务返回错误");
        } catch (Exception e) {
            log.error("Image detection API call failed", e);
            return buildFallbackResult("Image detection service unavailable 图像检测服务不可用");
        }
    }

    // ============================================================
    //  Composite Risk Assessment  综合风险评估
    // ============================================================

    /**
     * Call composite risk assessment API.
     * 调用综合风险评估API。
     *
     * @param textScore  text detection risk score (0-100)
     * @param voiceScore voice detection risk score (0-100)
     * @param imageScore image detection risk score (0-100)
     * @return assessment result map with riskScore, riskLevel, weights, detail
     */
    public Map<String, Object> assessRisk(int textScore, int voiceScore, int imageScore) {
        try {
            String url = baseUrl + "/api/assess/risk";
            Map<String, Object> body = new HashMap<>();
            body.put("textScore", textScore);
            body.put("voiceScore", voiceScore);
            body.put("imageScore", imageScore);

            ResponseEntity<Map> response = postJson(url, body, Map.class);
            return handleResponse(response);
        } catch (Exception e) {
            log.error("Risk assessment API call failed", e);
            return buildFallbackResult("Risk assessment service unavailable 风险评估服务不可用");
        }
    }

    // ============================================================
    //  Helper Methods  辅助方法
    // ============================================================

    /**
     * Send a JSON POST request.
     * 发送 JSON POST 请求。
     */
    private <T> ResponseEntity<T> postJson(String url, Object body, Class<T> responseType) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        HttpEntity<Object> entity = new HttpEntity<>(body, headers);
        return restTemplate.postForEntity(url, entity, responseType);
    }

    /**
     * Send a multipart file POST request.
     * 发送 multipart 文件上传 POST 请求。
     */
    private <T> ResponseEntity<T> postFile(String url, MultipartFile file, Class<T> responseType) {
        return postFile(url, file, null, responseType);
    }

    /**
     * Send a multipart file POST request with an optional model field.
     * 发送 multipart 文件上传 POST 请求，并可附带 model 表单字段。
     */
    private <T> ResponseEntity<T> postFile(String url, MultipartFile file, String model,
                                           Class<T> responseType) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);

        MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
        body.add("file", file.getResource());
        if (StringUtils.hasText(model)) {
            body.add("model", model.trim());
        }

        HttpEntity<MultiValueMap<String, Object>> entity = new HttpEntity<>(body, headers);
        return restTemplate.postForEntity(url, entity, responseType);
    }

    /**
     * Translate a Flask 4xx error (e.g. invalid/missing model) into a result map.
     * 将 Flask 的 4xx 错误（如模型名非法）透传为结果 Map，
     * 其中的 "error" 键供上层识别并返回 400。
     */
    @SuppressWarnings("unchecked")
    private Map<String, Object> handleClientError(HttpClientErrorException e, String fallbackDetail) {
        String raw = e.getResponseBodyAsString();
        if (StringUtils.hasText(raw)) {
            try {
                Map<String, Object> body = objectMapper.readValue(raw, Map.class);
                if (body != null) {
                    // Flask 的 error 字段是字符串消息；统一改写为布尔标记供上层识别，
                    // 原始文案保留在 detail 中
                    body.put("error", Boolean.TRUE);
                    return body;
                }
            } catch (Exception parseEx) {
                log.warn("Failed to parse AI service error body: {}", raw);
            }
        }
        Map<String, Object> result = buildFallbackResult(fallbackDetail);
        result.put("error", true);
        result.put("status", e.getStatusCode().value());
        return result;
    }

    /**
     * Handle API response and convert to a standard result map.
     * 处理API响应并转换为标准结果Map。
     */
    @SuppressWarnings("unchecked")
    private Map<String, Object> handleResponse(ResponseEntity<Map> response) {
        if (response.getStatusCode() != HttpStatus.OK || response.getBody() == null) {
            log.error("AI service returned non-OK status: {}", response.getStatusCode());
            return buildFallbackResult("AI service returned error AI服务返回错误");
        }
        return new HashMap<>(response.getBody());
    }

    /**
     * Build a fallback result when the AI service is unavailable.
     * 当AI服务不可用时构建降级返回结果。
     *
     * This implements the circuit breaker / graceful degradation pattern.
     * 实现了熔断/优雅降级模式。
     */
    private Map<String, Object> buildFallbackResult(String detail) {
        Map<String, Object> result = new HashMap<>();
        result.put("riskScore", 0);
        result.put("riskLevel", "检测失败");
        result.put("detail", detail);
        result.put("fallback", true);
        return result;
    }
}
