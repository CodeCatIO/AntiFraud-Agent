package com.cucn.springboot.exception;

import com.cucn.springboot.common.Constants;
import com.cucn.springboot.common.Result;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.validation.BindException;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.multipart.MaxUploadSizeExceededException;

import javax.validation.ConstraintViolation;
import javax.validation.ConstraintViolationException;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * Global Exception Handler
 * 全局异常处理器
 *
 * Catches all exceptions thrown by controllers and returns
 * a unified Result response to the frontend.
 * 捕获所有Controller抛出的异常，统一返回 Result 格式给前端。
 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    /**
     * Handle custom business exceptions (ServiceException).
     * 处理自定义业务异常。
     */
    @ExceptionHandler(ServiceException.class)
    public Result handleServiceException(ServiceException se) {
        log.warn("Business exception: code={}, msg={}", se.getCode(), se.getMessage());
        return Result.error(se.getCode(), se.getMessage());
    }

    /**
     * Handle validation exceptions for @RequestBody @Valid (JSON body).
     * 处理 @RequestBody @Valid 的参数校验异常（JSON请求体）。
     */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public Result handleValidationException(MethodArgumentNotValidException e) {
        List<FieldError> fieldErrors = e.getBindingResult().getFieldErrors();
        String msg = fieldErrors.stream()
                .map(error -> error.getField() + ": " + error.getDefaultMessage())
                .collect(Collectors.joining("; "));
        log.warn("Parameter validation failed: {}", msg);
        return Result.error(Constants.CODE_400, msg);
    }

    /**
     * Handle validation exceptions for form data (x-www-form-urlencoded).
     * 处理表单参数校验异常。
     */
    @ExceptionHandler(BindException.class)
    public Result handleBindException(BindException e) {
        List<FieldError> fieldErrors = e.getBindingResult().getFieldErrors();
        String msg = fieldErrors.stream()
                .map(error -> error.getField() + ": " + error.getDefaultMessage())
                .collect(Collectors.joining("; "));
        log.warn("Form binding validation failed: {}", msg);
        return Result.error(Constants.CODE_400, msg);
    }

    /**
     * Handle constraint violation exceptions (e.g., @RequestParam @Valid).
     * 处理路径变量/请求参数的校验异常。
     */
    @ExceptionHandler(ConstraintViolationException.class)
    public Result handleConstraintViolationException(ConstraintViolationException e) {
        Set<ConstraintViolation<?>> violations = e.getConstraintViolations();
        String msg = violations.stream()
                .map(v -> v.getPropertyPath() + ": " + v.getMessage())
                .collect(Collectors.joining("; "));
        log.warn("Constraint violation: {}", msg);
        return Result.error(Constants.CODE_400, msg);
    }

    /**
     * Handle file upload size limit exceptions.
     * 处理文件上传大小超限异常。
     */
    @ExceptionHandler(MaxUploadSizeExceededException.class)
    public Result handleMaxUploadSizeExceededException(MaxUploadSizeExceededException e) {
        log.warn("File upload size exceeded: {}", e.getMessage());
        return Result.error("413", "文件大小超过限制 File size exceeds the maximum allowed size");
    }

    /**
     * Handle illegal argument exceptions.
     * 处理非法参数异常。
     */
    @ExceptionHandler(IllegalArgumentException.class)
    public Result handleIllegalArgumentException(IllegalArgumentException e) {
        log.warn("Illegal argument: {}", e.getMessage());
        return Result.error(Constants.CODE_400, "参数错误: " + e.getMessage());
    }

    /**
     * Handle all other uncaught exceptions (catch-all).
     * 处理所有其他未捕获的异常（兜底）。
     */
    @ExceptionHandler(Exception.class)
    public Result handleException(Exception e) {
        log.error("System error", e);
        return Result.error(Constants.CODE_500, "系统内部错误 Internal server error");
    }
}
