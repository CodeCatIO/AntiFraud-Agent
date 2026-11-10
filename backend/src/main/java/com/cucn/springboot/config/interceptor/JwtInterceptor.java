package com.cucn.springboot.config.interceptor;

import cn.hutool.core.util.StrUtil;
import com.auth0.jwt.interfaces.DecodedJWT;
import com.cucn.springboot.common.Constants;
import com.cucn.springboot.config.AuthAccess;
import com.cucn.springboot.entity.User;
import com.cucn.springboot.exception.ServiceException;
import com.cucn.springboot.service.IUserService;
import com.cucn.springboot.utils.TokenUtils;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.method.HandlerMethod;
import org.springframework.web.servlet.HandlerInterceptor;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

/**
 * JWT Authentication Interceptor
 * JWT 认证拦截器
 *
 * Intercepts requests and validates JWT tokens for protected endpoints.
 * Uses TokenUtils for proper token validation including blacklist check.
 *
 * 拦截请求并验证受保护接口的JWT Token。
 * 使用 TokenUtils 进行完整的Token验证（包括黑名单检查）。
 *
 * Improvements:
 * - Uses shared secret key instead of per-user password
 * - Checks token blacklist (supports logout)
 * - Proper verification (not just decoding)
 *
 * 改进点：
 * - 使用共享密钥而非每个用户的密码
 * - 检查Token黑名单（支持登出）
 * - 正确的验证（不只是解码）
 */
@Slf4j
public class JwtInterceptor implements HandlerInterceptor {

    @Autowired
    private IUserService userService;

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) {
        String token = request.getHeader("token");
        String uri = request.getRequestURI();

        // Pass through if not mapping to a method (e.g. static resources)
        // 如果不是映射到方法直接通过（如静态资源）
        if (!(handler instanceof HandlerMethod)) {
            return true;
        }

        // Whitelist: Swagger / health / login / register / logout - no auth needed
        // 白名单：Swagger文档、健康检查、登录注册登出 不需要认证
        if (isWhitelisted(uri)) {
            log.debug("[JWT] Whitelisted URI: {}", uri);
            return true;
        }
        log.debug("[JWT] Intercepting URI: {}, handler type: {}", uri, handler.getClass().getSimpleName());

        // Check for @AuthAccess annotation - skip auth for those methods
        // 检查是否有 @AuthAccess 注解 —— 有就跳过认证
        HandlerMethod h = (HandlerMethod) handler;
        AuthAccess authAccess = h.getMethodAnnotation(AuthAccess.class);
        if (authAccess != null) {
            return true;
        }

        // Token presence check
        // 检查 Token 是否存在
        if (StrUtil.isBlank(token)) {
            throw new ServiceException(Constants.CODE_401, "无token，请重新登录");
        }

        // Validate token (signature, expiration, blacklist)
        // 验证 Token（签名、过期时间、黑名单）
        DecodedJWT decoded = TokenUtils.validateToken(token);
        if (decoded == null) {
            throw new ServiceException(Constants.CODE_401, "token验证失败，请重新登录");
        }

        // Get user ID from token and verify user exists
        // 从 Token 获取用户 ID 并验证用户存在
        String userId = decoded.getAudience().get(0);
        User user = userService.getById(userId);
        if (user == null) {
            throw new ServiceException(Constants.CODE_401, "用户不存在，请重新登录");
        }

        return true;
    }

    /**
     * Check if the request URI is in the whitelist (no auth required)
     * 检查请求URI是否在白名单中（无需认证）
     */
    private boolean isWhitelisted(String uri) {
        return uri.startsWith("/swagger-ui")
            || uri.startsWith("/swagger-resources")
            || uri.startsWith("/v2/api-docs")
            || uri.startsWith("/v3/api-docs")
            || uri.startsWith("/webjars")
            || uri.startsWith("/doc.html")
            || uri.equals("/swagger-ui.html")
            || uri.startsWith("/health")
            || uri.equals("/user/login")
            || uri.equals("/user/register")
            || uri.equals("/user/logout")
            || uri.startsWith("/file/")
            || uri.startsWith("/python/")
            || uri.startsWith("/DataTest/")
            || uri.startsWith("/detilebord/")
            || uri.startsWith("/message/")
            || uri.contains("/export")
            || uri.contains("/import");
    }
}
