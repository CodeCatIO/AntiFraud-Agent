package com.cucn.springboot.config;

import com.cucn.springboot.config.interceptor.JwtInterceptor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class InterceptorConfig implements WebMvcConfigurer {

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(jwtInterceptor())
                .addPathPatterns("/**")  // 拦截所有请求，通过判断token是否合法来决定是否需要登录
                .excludePathPatterns("/user/login", "/user/register", "/user/logout", "/**/export", "/**/import", "/file/**","/python/**","/DataTest/**","/detilebord/**","/message/**",
                        "/swagger-resources/**", "/webjars/**", "/v2/**", "/v3/**", "/swagger-ui.html", "/swagger-ui.html/**", "/swagger-ui/**", "/api", "/api-docs", "/api-docs/**", "/doc.html", "/doc.html/**")
                // Health check endpoints - no auth needed for monitoring
                .excludePathPatterns("/health", "/health/**")
                // Internal agent event callback - guarded by X-Agent-Service-Token, not user JWT
                .excludePathPatterns("/internal/agent/**")
                .excludePathPatterns( "/**/*.html", "/**/*.js", "/**/*.css", "/**/*.woff", "/**/*.ttf", "/**/*.png", "/**/*.jpg", "/**/*.svg", "/**/*.ico");


    }

    @Bean
    public JwtInterceptor jwtInterceptor() {
        return new JwtInterceptor();
    }

}
