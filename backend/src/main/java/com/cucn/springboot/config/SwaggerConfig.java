package com.cucn.springboot.config;

import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import springfox.documentation.builders.ApiInfoBuilder;
import springfox.documentation.builders.PathSelectors;
import springfox.documentation.builders.RequestHandlerSelectors;
import springfox.documentation.service.ApiInfo;
import springfox.documentation.service.ApiKey;
import springfox.documentation.service.AuthorizationScope;
import springfox.documentation.service.Contact;
import springfox.documentation.service.SecurityReference;
import springfox.documentation.spi.DocumentationType;
import springfox.documentation.spring.web.plugins.Docket;
import springfox.documentation.swagger2.annotations.EnableSwagger2;

import javax.annotation.PostConstruct;
import java.util.Collections;

import springfox.documentation.spi.service.contexts.SecurityContext;

@Slf4j
@Configuration
@EnableSwagger2
public class SwaggerConfig {

    @PostConstruct
    public void init() {
        log.info("========================================");
        log.info("  Swagger Config initialized successfully");
        log.info("  Swagger配置初始化成功");
        log.info("========================================");
    }

    @Bean
    public Docket createRestApi() {
        return new Docket(DocumentationType.SWAGGER_2)
                .apiInfo(apiInfo())
                .select()
                .apis(RequestHandlerSelectors.basePackage("com.cucn.springboot.controller"))
                .paths(PathSelectors.any())
                .build()
                // 让 Swagger UI 出现 Authorize 按钮，请求头名称为自定义的 token
                .securitySchemes(Collections.singletonList(apiKey()))
                .securityContexts(Collections.singletonList(securityContext()));
    }

    private ApiKey apiKey() {
        // name: 安全方案名；keyname: 请求头名；passAs: 放在 header
        return new ApiKey("token", "token", "header");
    }

    private SecurityContext securityContext() {
        return SecurityContext.builder()
                .securityReferences(Collections.singletonList(defaultAuth()))
                .forPaths(PathSelectors.any())
                .build();
    }

    private SecurityReference defaultAuth() {
        AuthorizationScope scope = new AuthorizationScope("global", "accessEverything");
        return new SecurityReference("token", new AuthorizationScope[]{scope});
    }

    private ApiInfo apiInfo() {
        return new ApiInfoBuilder()
                .title("AI Anti-Fraud Detection System API")
                .description("AI反诈骗检测系统接口文档")
                .contact(new Contact("Dev Team", "", ""))
                .version("2.0")
                .build();
    }
}
