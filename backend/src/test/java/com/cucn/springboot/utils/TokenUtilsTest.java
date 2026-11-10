package com.cucn.springboot.utils;

import com.auth0.jwt.JWT;
import com.auth0.jwt.interfaces.DecodedJWT;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Unit tests for TokenUtils (JWT functionality)
 * TokenUtils 单元测试（JWT功能）
 *
 * Tests token generation, validation, and basic properties.
 * Note: Redis-dependent features (blacklist) require integration test.
 * 测试 Token 生成、验证等基本功能。Redis相关功能（黑名单）需集成测试。
 */
@DisplayName("TokenUtils Tests - JWT Token工具测试")
class TokenUtilsTest {

    @BeforeEach
    void setUp() {
        // Set static fields via reflection for testing
        // 通过反射设置静态字段用于测试
        ReflectionTestUtils.setField(TokenUtils.class, "jwtSecret", "test-secret-key-for-unit-tests");
        ReflectionTestUtils.setField(TokenUtils.class, "expireHours", 24);
    }

    @Test
    @DisplayName("Generate token and extract user ID - 生成Token并提取用户ID")
    void testGenTokenAndExtractUserId() {
        String userId = "12345";
        String token = TokenUtils.genToken(userId);

        assertNotNull(token, "Token should not be null");
        assertFalse(token.isEmpty(), "Token should not be empty");

        // Decode and verify user ID
        DecodedJWT decoded = JWT.decode(token);
        assertEquals(userId, decoded.getAudience().get(0),
                "Token should contain correct user ID");
    }

    @Test
    @DisplayName("Token validation with correct signature - Token签名验证")
    void testValidateToken() {
        String userId = "67890";
        String token = TokenUtils.genToken(userId);

        // Without Redis (blacklist check will be skipped), validation should pass
        // 没有Redis时（跳过黑名单检查），验证应该通过
        DecodedJWT decoded = TokenUtils.validateToken(token);
        assertNotNull(decoded, "Valid token should pass validation");
        assertEquals(userId, decoded.getAudience().get(0));
    }

    @Test
    @DisplayName("Invalid token should fail validation - 无效Token验证失败")
    void testInvalidToken() {
        assertNull(TokenUtils.validateToken(null), "Null token should be invalid");
        assertNull(TokenUtils.validateToken(""), "Empty token should be invalid");
        assertNull(TokenUtils.validateToken("not.a.valid.token"),
                "Malformed token should be invalid");
    }

    @Test
    @DisplayName("Token with wrong signature should fail - 错误签名的Token验证失败")
    void testWrongSignature() {
        // Generate a token with a different secret
        // 用不同的密钥生成token
        String fakeToken = JWT.create()
                .withAudience("123")
                .sign(com.auth0.jwt.algorithms.Algorithm.HMAC256("wrong-secret"));

        DecodedJWT result = TokenUtils.validateToken(fakeToken);
        assertNull(result, "Token with wrong signature should fail validation");
    }

    @Test
    @DisplayName("Token expiration time - Token过期时间")
    void testTokenExpiration() {
        String token = TokenUtils.genToken("1");

        long ttlSeconds = TokenUtils.getTokenExpireSeconds(token);
        assertTrue(ttlSeconds > 0, "New token should have positive TTL");
        assertTrue(ttlSeconds <= 24 * 60 * 60,
                "Token TTL should not exceed 24 hours");
    }
}
