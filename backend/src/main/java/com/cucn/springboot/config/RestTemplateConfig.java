package com.cucn.springboot.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestTemplate;

/**
 * RestTemplate Configuration for AI Service Communication
 *
 * Configures a RestTemplate with proper timeout settings
 * for calling the Python AI detection microservice.
 *
 * 配置用于调用Python AI检测微服务的RestTemplate，含超时设置。
 */
@Configuration
public class RestTemplateConfig {

    @Value("${files.ai-service.connect-timeout:5000}")
    private int connectTimeout;

    @Value("${files.ai-service.read-timeout:30000}")
    private int readTimeout;

    @Bean
    public RestTemplate aiServiceRestTemplate() {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(connectTimeout);
        factory.setReadTimeout(readTimeout);
        return new RestTemplate(factory);
    }
}
