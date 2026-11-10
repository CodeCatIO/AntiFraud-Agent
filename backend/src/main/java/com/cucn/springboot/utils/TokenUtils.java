package com.cucn.springboot.utils;

import cn.hutool.core.date.DateUtil;
import cn.hutool.core.util.StrUtil;
import com.auth0.jwt.JWT;
import com.auth0.jwt.algorithms.Algorithm;
import com.auth0.jwt.exceptions.JWTVerificationException;
import com.auth0.jwt.interfaces.DecodedJWT;
import com.auth0.jwt.interfaces.JWTVerifier;
import com.cucn.springboot.entity.User;
import com.cucn.springboot.service.IUserService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;

import javax.annotation.PostConstruct;
import javax.annotation.Resource;
import javax.servlet.http.HttpServletRequest;
import java.util.Date;
import java.util.concurrent.TimeUnit;

/**
 * JWT Token Utility
 * JWT Token 工具类
 *
 * Provides token generation, validation, and blacklist management.
 * Uses a configurable secret key and Redis-based token blacklist for logout.
 *
 * 提供 Token 生成、验证和黑名单管理。
 * 使用可配置的密钥 + 基于Redis的Token黑名单实现登出功能。
 *
 * Improvements over original:
 * 1. Dedicated secret key (not user's password)
 * 2. Configurable expiration time
 * 3. Token blacklist via Redis for proper logout
 * 4. Proper token verification (not just decoding)
 *
 * 改进点：
 * 1. 专用密钥（不再用用户密码当密钥）
 * 2. 可配置的过期时间
 * 3. 基于Redis的Token黑名单，支持真正的登出
 * 4. 正确的Token验证（不只是解码）
 */
@Slf4j
@Component
public class TokenUtils {

    private static IUserService staticUserService;
    private static StringRedisTemplate staticRedisTemplate;

    /**
     * JWT secret key - loaded from config
     * JWT 密钥 - 从配置加载
     */
    private static String jwtSecret;

    /**
     * Token expiration time in hours
     * Token 过期时间（小时）
     */
    private static int expireHours;

    /**
     * Redis key prefix for token blacklist
     * Token黑名单的Redis键前缀
     */
    private static final String TOKEN_BLACKLIST_PREFIX = "token:blacklist:";

    @Resource
    private IUserService userService;

    @Resource
    private StringRedisTemplate stringRedisTemplate;

    @Value("${jwt.secret:anti-fraud-secret-key-2024}")
    private String secret;

    @Value("${jwt.expire-hours:24}")
    private int expireHrs;

    @PostConstruct
    public void init() {
        staticUserService = userService;
        staticRedisTemplate = stringRedisTemplate;
        jwtSecret = secret;
        expireHours = expireHrs;
    }

    // ============================================================
    //  Token Generation  Token 生成
    // ============================================================

    /**
     * Generate a JWT token for a user.
     * 为用户生成 JWT Token。
     *
     * @param userId user ID
     * @return JWT token string
     */
    public static String genToken(String userId) {
        return JWT.create()
                .withAudience(userId)              // Store user ID in payload
                .withIssuedAt(new Date())          // Issue time
                .withExpiresAt(DateUtil.offsetHour(new Date(), expireHours))
                .sign(Algorithm.HMAC256(jwtSecret));
    }

    /**
     * @deprecated Use genToken(userId) instead.
     *             Kept for backward compatibility with old code.
     * 旧方法，保留向后兼容。第二个参数忽略。
     */
    @Deprecated
    public static String genToken(String userId, String sign) {
        return genToken(userId);
    }

    // ============================================================
    //  Token Validation  Token 验证
    // ============================================================

    /**
     * Validate a JWT token.
     * 验证 JWT Token 是否有效。
     *
     * Checks:
     * 1. Token format is valid
     * 2. Signature is correct
     * 3. Token is not expired
     * 4. Token is not in blacklist
     *
     * @param token JWT token string
     * @return decoded JWT if valid, null if invalid
     */
    public static DecodedJWT validateToken(String token) {
        if (StrUtil.isBlank(token)) {
            return null;
        }

        // Check if token is blacklisted (logged out)
        // 检查 Token 是否在黑名单中（已登出）
        if (isTokenBlacklisted(token)) {
            log.warn("Token is blacklisted (user logged out)");
            return null;
        }

        try {
            Algorithm algorithm = Algorithm.HMAC256(jwtSecret);
            JWTVerifier verifier = JWT.require(algorithm).build();
            return verifier.verify(token);
        } catch (JWTVerificationException e) {
            log.warn("Token verification failed: {}", e.getMessage());
            return null;
        }
    }

    // ============================================================
    //  Current User  获取当前用户
    // ============================================================

    /**
     * Get current logged-in user from request token.
     * 从请求的 Token 中获取当前登录用户。
     *
     * @return User object if valid token, null otherwise
     */
    public static User getCurrentUser() {
        try {
            HttpServletRequest request = ((ServletRequestAttributes)
                    RequestContextHolder.getRequestAttributes()).getRequest();
            String token = request.getHeader("token");
            if (StrUtil.isNotBlank(token)) {
                DecodedJWT decoded = validateToken(token);
                if (decoded != null) {
                    String userId = decoded.getAudience().get(0);
                    return staticUserService.getById(Integer.valueOf(userId));
                }
            }
        } catch (Exception e) {
            log.warn("Failed to get current user from token: {}", e.getMessage());
            return null;
        }
        return null;
    }

    // ============================================================
    //  Token Blacklist  Token 黑名单（登出用）
    // ============================================================

    /**
     * Invalidate a token by adding it to the Redis blacklist.
     * 将 Token 加入 Redis 黑名单，使其失效。
     *
     * Used for logout functionality.
     * The token will be automatically removed from Redis after it expires.
     *
     * 用于登出功能。Token过期后会自动从Redis中删除。
     *
     * @param token JWT token to invalidate
     */
    public static void invalidateToken(String token) {
        if (StrUtil.isBlank(token) || staticRedisTemplate == null) {
            return;
        }

        try {
            DecodedJWT decoded = JWT.decode(token);
            Date expiresAt = decoded.getExpiresAt();
            long ttlSeconds = (expiresAt.getTime() - System.currentTimeMillis()) / 1000;

            if (ttlSeconds > 0) {
                String key = TOKEN_BLACKLIST_PREFIX + token;
                staticRedisTemplate.opsForValue().set(key, "1", ttlSeconds, TimeUnit.SECONDS);
                log.info("Token added to blacklist, TTL={}s", ttlSeconds);
            }
        } catch (Exception e) {
            log.warn("Failed to invalidate token: {}", e.getMessage());
        }
    }

    /**
     * Check if a token is in the blacklist.
     * 检查 Token 是否在黑名单中。
     */
    private static boolean isTokenBlacklisted(String token) {
        if (staticRedisTemplate == null) return false;
        try {
            String key = TOKEN_BLACKLIST_PREFIX + token;
            return Boolean.TRUE.equals(staticRedisTemplate.hasKey(key));
        } catch (Exception e) {
            log.warn("Redis error checking token blacklist: {}", e.getMessage());
            return false;
        }
    }

    /**
     * Get remaining expiration time of a token in seconds.
     * 获取 Token 剩余有效时间（秒）。
     */
    public static long getTokenExpireSeconds(String token) {
        try {
            DecodedJWT decoded = JWT.decode(token);
            long ttl = (decoded.getExpiresAt().getTime() - System.currentTimeMillis()) / 1000;
            return Math.max(0, ttl);
        } catch (Exception e) {
            return 0;
        }
    }
}
