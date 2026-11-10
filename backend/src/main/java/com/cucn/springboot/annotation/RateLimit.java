package com.cucn.springboot.annotation;

import java.lang.annotation.*;

/**
 * Rate Limit Annotation
 * 接口限流注解
 *
 * Apply this annotation to controller methods that need rate limiting.
 * Uses Redis counter-based rate limiting.
 *
 * 把此注解加在需要限流的 Controller 方法上。
 * 使用基于Redis计数器的限流算法。
 *
 * Usage example:
 *   @RateLimit(key = "login", limit = 5, period = 60)
 *   // 60秒内最多5次登录请求
 */
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
@Documented
public @interface RateLimit {

    /**
     * Rate limit key prefix (combined with IP/user to form unique key)
     * 限流键前缀（与IP/用户组合成唯一key）
     */
    String key() default "";

    /**
     * Maximum number of requests allowed within the period
     * 时间窗口内允许的最大请求数
     */
    int limit() default 10;

    /**
     * Time period in seconds
     * 时间窗口（秒）
     */
    int period() default 60;

    /**
     * Whether to limit by user (true) or by IP (false)
     * true=按用户限流，false=按IP限流
     */
    boolean byUser() default true;
}
