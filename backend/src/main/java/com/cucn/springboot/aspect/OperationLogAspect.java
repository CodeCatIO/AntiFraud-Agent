package com.cucn.springboot.aspect;

import com.cucn.springboot.annotation.OpLog;
import com.cucn.springboot.entity.OperationLog;
import com.cucn.springboot.entity.User;
import com.cucn.springboot.mapper.OperationLogMapper;
import com.cucn.springboot.utils.TokenUtils;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.aspectj.lang.reflect.MethodSignature;
import org.springframework.stereotype.Component;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;
import org.springframework.web.multipart.MultipartFile;

import javax.annotation.Resource;
import javax.servlet.http.HttpServletRequest;
import java.lang.reflect.Method;
import java.util.Date;
import java.util.HashMap;
import java.util.Map;

/**
 * Operation Log Aspect (AOP)
 * 操作日志切面（AOP实现）
 *
 * Intercepts methods annotated with @OpLog and records the operation
 * to the database for audit purposes.
 *
 * 拦截被 @OpLog 注解标记的方法，将操作记录存入数据库用于审计。
 *
 * Recorded information:
 * - Who: user ID, username, IP
 * - What: module, type, description, method, URL, parameters
 * - Result: success/failure, error message, execution time
 */
@Slf4j
@Aspect
@Component
public class OperationLogAspect {

    @Resource
    private OperationLogMapper operationLogMapper;

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Around("@annotation(com.cucn.springboot.annotation.OpLog)")
    public Object logOperation(ProceedingJoinPoint joinPoint) throws Throwable {
        long startTime = System.currentTimeMillis();

        MethodSignature signature = (MethodSignature) joinPoint.getSignature();
        Method method = signature.getMethod();
        OpLog annotation = method.getAnnotation(OpLog.class);

        // Build the log entry
        OperationLog operationLog = new OperationLog();
        operationLog.setModule(annotation.module());
        operationLog.setType(annotation.type());
        operationLog.setDescription(annotation.desc());
        operationLog.setMethod(getRequestMethod());
        operationLog.setUrl(getRequestUrl());
        operationLog.setIp(getClientIp());
        operationLog.setCreateTime(new Date());

        // Set user info if available
        try {
            User currentUser = TokenUtils.getCurrentUser();
            if (currentUser != null) {
                operationLog.setUserId(currentUser.getId());
                operationLog.setUsername(currentUser.getUsername());
            }
        } catch (Exception e) {
            // Ignore - might be public endpoint like login
        }

        // Record request parameters (mask sensitive fields)
        try {
            String params = buildParamsJson(joinPoint, signature);
            operationLog.setParams(params);
        } catch (Exception e) {
            operationLog.setParams("{}");
        }

        Object result = null;

        try {
            result = joinPoint.proceed();
            operationLog.setResult("success");
            return result;
        } catch (Throwable t) {
            operationLog.setResult("fail");
            operationLog.setErrorMsg(t.getMessage());
            throw t;
        } finally {
            // Calculate execution time and save log
            long costTime = System.currentTimeMillis() - startTime;
            operationLog.setCostTime(costTime);

            try {
                operationLogMapper.insert(operationLog);
            } catch (Exception e) {
                // Don't let log failure affect business logic
                log.error("Failed to save operation log: {}", e.getMessage());
            }
        }
    }

    // ============================================================
    //  Helper Methods
    // ============================================================

    private String getRequestMethod() {
        try {
            return getRequest().getMethod();
        } catch (Exception e) {
            return "";
        }
    }

    private String getRequestUrl() {
        try {
            return getRequest().getRequestURI();
        } catch (Exception e) {
            return "";
        }
    }

    private String getClientIp() {
        try {
            HttpServletRequest request = getRequest();
            String ip = request.getHeader("X-Forwarded-For");
            if (ip == null || ip.isEmpty() || "unknown".equalsIgnoreCase(ip)) {
                ip = request.getHeader("X-Real-IP");
            }
            if (ip == null || ip.isEmpty() || "unknown".equalsIgnoreCase(ip)) {
                ip = request.getRemoteAddr();
            }
            if (ip != null && ip.contains(",")) {
                ip = ip.split(",")[0].trim();
            }
            return ip != null ? ip : "unknown";
        } catch (Exception e) {
            return "unknown";
        }
    }

    private HttpServletRequest getRequest() {
        ServletRequestAttributes attrs = (ServletRequestAttributes)
                RequestContextHolder.getRequestAttributes();
        return attrs != null ? attrs.getRequest() : null;
    }

    /**
     * Build JSON string of method parameters, masking sensitive fields.
     */
    private String buildParamsJson(ProceedingJoinPoint joinPoint, MethodSignature signature) {
        String[] paramNames = signature.getParameterNames();
        Object[] paramValues = joinPoint.getArgs();

        Map<String, Object> params = new HashMap<>();
        for (int i = 0; i < paramNames.length; i++) {
            String name = paramNames[i];
            Object value = paramValues[i];

            if (value instanceof MultipartFile) {
                params.put(name, "[FILE]");
                continue;
            }
            if (value instanceof HttpServletRequest) {
                continue;
            }

            if (isSensitiveField(name) && value != null) {
                params.put(name, "********");
            } else {
                params.put(name, value);
            }
        }

        try {
            return objectMapper.writeValueAsString(params);
        } catch (Exception e) {
            return "{}";
        }
    }

    private boolean isSensitiveField(String fieldName) {
        String lower = fieldName.toLowerCase();
        return lower.contains("password")
                || lower.contains("token")
                || lower.contains("secret")
                || lower.contains("private");
    }
}
