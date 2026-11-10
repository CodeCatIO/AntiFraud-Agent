package com.cucn.springboot.aspect;

import com.cucn.springboot.annotation.RateLimit;
import com.cucn.springboot.exception.ServiceException;
import com.cucn.springboot.utils.TokenUtils;
import lombok.extern.slf4j.Slf4j;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.aspectj.lang.reflect.MethodSignature;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;

import javax.annotation.Resource;
import javax.servlet.http.HttpServletRequest;
import java.lang.reflect.Method;
import java.util.concurrent.TimeUnit;

/**
 * Rate Limiting Aspect (AOP)
 * 限流切面（AOP实现）
 *
 * Intercepts methods annotated with @RateLimit and enforces rate limiting
 * using Redis atomic counters with TTL-based time windows.
 *
 * 拦截被 @RateLimit 注解标记的方法，使用Redis原子计数器 + TTL时间窗口实现限流。
 *
 * Algorithm: Fixed window counter
 * - Each unique key has a counter in Redis
 * - Counter auto-expires after the period (time window)
 * - Each request increments the counter; if limit is exceeded, reject
 *
 * 算法：固定窗口计数器
 * - 每个唯一键在Redis中有一个计数器
 * - 计数器在时间窗口结束后自动过期
 * - 每次请求计数器+1，超过限制则拒绝
 */
@Slf4j
@Aspect
@Component
public class RateLimitAspect {

    @Resource
    private StringRedisTemplate stringRedisTemplate;

    private static final String RATE_LIMIT_PREFIX = "rate:limit:";

    @Around("@annotation(com.cucn.springboot.annotation.RateLimit)")
    public Object rateLimit(ProceedingJoinPoint joinPoint) throws Throwable {
        MethodSignature signature = (MethodSignature) joinPoint.getSignature();
        Method method = signature.getMethod();
        RateLimit rateLimit = method.getAnnotation(RateLimit.class);

        if (rateLimit == null) {
            return joinPoint.proceed();
        }

        // Build the rate limit key
        // 构建限流键
        String key = buildRateLimitKey(rateLimit, method);

        // Try to increment the counter
        // 尝试增加计数器
        Long count = stringRedisTemplate.opsForValue().increment(key);

        // If this is the first request, set the expiration
        // 如果是第一次请求，设置过期时间
        if (count != null && count == 1) {
            stringRedisTemplate.expire(key, rateLimit.period(), TimeUnit.SECONDS);
        }

        // Check if limit is exceeded
        // 检查是否超过限制
        if (count != null && count > rateLimit.limit()) {
            log.warn("Rate limit exceeded: key={}, count={}, limit={}/{}s",
                    key, count, rateLimit.limit(), rateLimit.period());
            throw new ServiceException("429",
                    "请求过于频繁，请稍后再试 Too many requests, please try again later");
        }

        return joinPoint.proceed();
    }

    /**
     * Build a unique rate limit key.
     * 构建唯一的限流键。
     *
     * Format: rate:limit:{methodKey}:{identifier}
     * Identifier is user ID (if byUser=true and user is logged in) or client IP.
     *
     * 标识符为用户ID（如果byUser=true且已登录）或客户端IP。
     */
    private String buildRateLimitKey(RateLimit rateLimit, Method method) {
        String methodKey = rateLimit.key();
        if (methodKey.isEmpty()) {
            methodKey = method.getDeclaringClass().getSimpleName() + "." + method.getName();
        }

        String identifier;
        if (rateLimit.byUser()) {
            // Try to get user ID from token
            // 尝试从token获取用户ID
            try {
                Integer userId = TokenUtils.getCurrentUser().getId();
                identifier = "user:" + userId;
            } catch (Exception e) {
                // Fall back to IP if not logged in
                // 未登录则回退到IP
                identifier = "ip:" + getClientIp();
            }
        } else {
            identifier = "ip:" + getClientIp();
        }

        return RATE_LIMIT_PREFIX + methodKey + ":" + identifier;
    }

    /**
     * Get client IP address from request.
     * 从请求中获取客户端IP地址。
     */
    private String getClientIp() {
        try {
            HttpServletRequest request = ((ServletRequestAttributes)
                    RequestContextHolder.getRequestAttributes()).getRequest();
            String ip = request.getHeader("X-Forwarded-For");
            if (ip == null || ip.isEmpty() || "unknown".equalsIgnoreCase(ip)) {
                ip = request.getHeader("X-Real-IP");
            }
            if (ip == null || ip.isEmpty() || "unknown".equalsIgnoreCase(ip)) {
                ip = request.getRemoteAddr();
            }
            // If multiple IPs (proxy chain), take the first one
            // 如果有多个IP（代理链），取第一个
            if (ip != null && ip.contains(",")) {
                ip = ip.split(",")[0].trim();
            }
            return ip != null ? ip : "unknown";
        } catch (Exception e) {
            return "unknown";
        }
    }
}
