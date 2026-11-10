package com.cucn.springboot.utils;

import cn.hutool.crypto.SecureUtil;
import cn.hutool.crypto.digest.BCrypt;

/**
 * Password Encoding Utility
 * 密码加密工具类
 *
 * Uses BCrypt for secure password hashing (recommended for production).
 * Also supports backward compatibility with legacy MD5 hashes for migration.
 *
 * 使用 BCrypt 进行安全的密码哈希（生产环境推荐）。
 * 同时支持向后兼容旧的 MD5 哈希，用于平滑迁移。
 *
 * Why BCrypt is better than MD5:
 * 1. Salted: automatically adds random salt, no two same passwords have same hash
 * 2. Slow: computationally expensive, resistant to brute-force attacks
 * 3. Adaptive: work factor can be increased as hardware gets faster
 *
 * 为什么 BCrypt 比 MD5 好：
 * 1. 加盐：自动添加随机盐，相同密码哈希值也不同
 * 2. 慢速：计算开销大，抗暴力破解
 * 3. 自适应：硬件提升时可以增加工作因子
 */
public class PasswordEncoderUtil {

    /**
     * Encode a raw password using BCrypt.
     * 用 BCrypt 加密明文密码。
     *
     * @param rawPassword plain text password
     * @return BCrypt hashed password
     */
    public static String encode(String rawPassword) {
        return BCrypt.hashpw(rawPassword, BCrypt.gensalt());
    }

    /**
     * Verify a raw password against a BCrypt hash.
     * 验证明文密码是否匹配 BCrypt 哈希。
     *
     * @param rawPassword  plain text password
     * @param encodedPassword BCrypt hashed password from database
     * @return true if matches
     */
    public static boolean matches(String rawPassword, String encodedPassword) {
        if (rawPassword == null || encodedPassword == null) {
            return false;
        }
        try {
            return BCrypt.checkpw(rawPassword, encodedPassword);
        } catch (Exception e) {
            // If the stored hash is not valid BCrypt, it might be legacy MD5
            // 如果存储的不是有效BCrypt哈希，可能是旧的MD5格式
            return false;
        }
    }

    /**
     * Check if a stored password hash is in BCrypt format.
     * 检查存储的密码哈希是否为 BCrypt 格式。
     *
     * BCrypt hashes start with $2a$, $2b$, or $2y$
     * BCrypt 哈希以 $2a$、$2b$ 或 $2y$ 开头
     */
    public static boolean isBcryptHash(String hash) {
        return hash != null && (hash.startsWith("$2a$") || hash.startsWith("$2b$") || hash.startsWith("$2y$"));
    }

    /**
     * Verify against legacy MD5 hash (for migration purposes).
     * 用旧版 MD5 哈希验证（用于迁移）。
     *
     * @param rawPassword plain text password
     * @param md5Hash MD5 hashed password
     * @return true if matches
     */
    public static boolean matchesMd5(String rawPassword, String md5Hash) {
        if (rawPassword == null || md5Hash == null) {
            return false;
        }
        return SecureUtil.md5(rawPassword).equals(md5Hash);
    }

    /**
     * Smart verify: tries BCrypt first, falls back to MD5 for legacy users.
     * 智能验证：先试 BCrypt，失败则回退到 MD5（兼容老用户）。
     *
     * @param rawPassword plain text password
     * @param storedHash  stored password hash (could be BCrypt or MD5)
     * @return true if matches
     */
    public static boolean smartMatches(String rawPassword, String storedHash) {
        if (storedHash == null) return false;

        // Try BCrypt first (if it looks like BCrypt)
        // 先试 BCrypt（如果看起来像BCrypt格式）
        if (isBcryptHash(storedHash)) {
            return matches(rawPassword, storedHash);
        }

        // Fall back to MD5 for legacy users
        // 回退到 MD5（老用户）
        return matchesMd5(rawPassword, storedHash);
    }

    /**
     * Check if the stored password needs migration from MD5 to BCrypt.
     * 检查存储的密码是否需要从 MD5 迁移到 BCrypt。
     */
    public static boolean needsMigration(String storedHash) {
        return !isBcryptHash(storedHash);
    }
}
