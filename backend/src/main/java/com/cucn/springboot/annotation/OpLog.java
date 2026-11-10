package com.cucn.springboot.annotation;

import java.lang.annotation.*;

/**
 * Operation Log Annotation
 * 操作日志注解
 *
 * Apply this annotation to controller methods that need audit logging.
 * The AOP aspect will automatically record the operation.
 *
 * 把此注解加在需要审计日志的 Controller 方法上。
 * AOP切面会自动记录操作日志。
 *
 * Usage example:
 *   @OpLog(module = "user", type = "login", desc = "用户登录")
 */
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
@Documented
public @interface OpLog {

    /** Module name 模块名称 */
    String module() default "";

    /** Operation type 操作类型 e.g. login, create, update, delete */
    String type() default "";

    /** Operation description 操作描述 */
    String desc() default "";
}
