package com.cucn.springboot.utils;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Unit tests for PasswordEncoderUtil
 * 密码加密工具类单元测试
 *
 * Tests BCrypt encoding, verification, and MD5 backward compatibility.
 * 测试 BCrypt 加密、验证，以及 MD5 向后兼容性。
 */
@DisplayName("PasswordEncoderUtil Tests - 密码加密工具测试")
class PasswordEncoderUtilTest {

    @Test
    @DisplayName("BCrypt encode and verify - BCrypt加密与验证")
    void testBcryptEncodeAndMatch() {
        String rawPassword = "TestPass123!";
        String encoded = PasswordEncoderUtil.encode(rawPassword);

        // BCrypt hash always starts with $2a$
        assertTrue(PasswordEncoderUtil.isBcryptHash(encoded),
                "Encoded password should be BCrypt format");

        // Correct password should match
        assertTrue(PasswordEncoderUtil.matches(rawPassword, encoded),
                "Correct password should match");

        // Wrong password should NOT match
        assertFalse(PasswordEncoderUtil.matches("WrongPass", encoded),
                "Wrong password should not match");
    }

    @Test
    @DisplayName("Same password, different hashes (salt) - 相同密码生成不同哈希（加盐）")
    void testBcryptSaltUniqueness() {
        String password = "samePassword";
        String hash1 = PasswordEncoderUtil.encode(password);
        String hash2 = PasswordEncoderUtil.encode(password);

        // Same password should produce different hashes (because of random salt)
        assertNotEquals(hash1, hash2,
                "Same password should produce different hashes due to salt");

        // Both hashes should verify the original password
        assertTrue(PasswordEncoderUtil.matches(password, hash1));
        assertTrue(PasswordEncoderUtil.matches(password, hash2));
    }

    @Test
    @DisplayName("MD5 backward compatibility - MD5向后兼容")
    void testMd5BackwardCompatibility() {
        String password = "legacyUser123";
        String md5Hash = cn.hutool.crypto.SecureUtil.md5(password);

        // MD5 hash should NOT be recognized as BCrypt
        assertFalse(PasswordEncoderUtil.isBcryptHash(md5Hash),
                "MD5 hash should not be recognized as BCrypt");

        // MD5 hash should need migration
        assertTrue(PasswordEncoderUtil.needsMigration(md5Hash),
                "MD5 hash should need migration");

        // smartMatches should work with MD5 hash
        assertTrue(PasswordEncoderUtil.smartMatches(password, md5Hash),
                "smartMatches should work with MD5 hash");

        // BCrypt hash should NOT need migration
        String bcryptHash = PasswordEncoderUtil.encode(password);
        assertFalse(PasswordEncoderUtil.needsMigration(bcryptHash),
                "BCrypt hash should not need migration");
    }

    @Test
    @DisplayName("Smart matching - 智能匹配（BCrypt优先，MD5兜底）")
    void testSmartMatches() {
        String password = "SmartTest123";

        // BCrypt case
        String bcryptHash = PasswordEncoderUtil.encode(password);
        assertTrue(PasswordEncoderUtil.smartMatches(password, bcryptHash),
                "smartMatches should work with BCrypt hash");

        // MD5 case
        String md5Hash = cn.hutool.crypto.SecureUtil.md5(password);
        assertTrue(PasswordEncoderUtil.smartMatches(password, md5Hash),
                "smartMatches should work with MD5 hash");

        // Wrong password
        assertFalse(PasswordEncoderUtil.smartMatches("wrong", bcryptHash));
        assertFalse(PasswordEncoderUtil.smartMatches("wrong", md5Hash));
    }

    @Test
    @DisplayName("Null and empty handling - 空值处理")
    void testNullAndEmpty() {
        assertFalse(PasswordEncoderUtil.matches(null, null));
        assertFalse(PasswordEncoderUtil.matches("", null));
        assertFalse(PasswordEncoderUtil.matches("test", null));
        assertFalse(PasswordEncoderUtil.smartMatches("test", null));
        assertFalse(PasswordEncoderUtil.isBcryptHash(null));
        assertFalse(PasswordEncoderUtil.needsMigration(null));
    }

    @Test
    @DisplayName("Empty password edge case - 空密码边界测试")
    void testEmptyPassword() {
        String empty = "";
        String encoded = PasswordEncoderUtil.encode(empty);
        assertTrue(PasswordEncoderUtil.matches(empty, encoded));
        assertFalse(PasswordEncoderUtil.matches(" ", encoded));
    }
}
