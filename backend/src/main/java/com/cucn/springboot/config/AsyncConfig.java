package com.cucn.springboot.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;

import java.util.concurrent.Executor;
import java.util.concurrent.ThreadPoolExecutor;

/**
 * Async Configuration for AI Detection Tasks
 * 异步任务配置 - 用于AI检测任务
 *
 * Configures a dedicated thread pool for async AI detection operations
 * such as voice and image analysis which may take longer time.
 *
 * 为异步AI检测操作（如语音和图像分析，可能耗时较长）配置专用线程池。
 *
 * Why use a dedicated thread pool?
 * - Prevents blocking the main request-handling threads
 * - Controls concurrency to avoid overwhelming the AI service
 * - Allows for better resource management and monitoring
 *
 * 为什么用专用线程池？
 * - 防止阻塞主请求处理线程
 * - 控制并发量，避免压垮AI服务
 * - 更好的资源管理和监控
 */
@Configuration
@EnableAsync
public class AsyncConfig {

    @Bean("aiDetectionExecutor")
    public Executor aiDetectionExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();

        // Core pool size: number of threads kept alive
        // 核心线程数：保持存活的线程数
        executor.setCorePoolSize(4);

        // Max pool size: maximum number of threads
        // 最大线程数：最多线程数
        executor.setMaxPoolSize(10);

        // Queue capacity: how many tasks can be queued when all threads are busy
        // 队列容量：所有线程忙时，可以排队的任务数
        executor.setQueueCapacity(50);

        // Thread name prefix for easy identification in logs
        // 线程名前缀，便于在日志中识别
        executor.setThreadNamePrefix("ai-detect-");

        // Keep alive time for idle threads above core pool size
        // 超过核心线程数的空闲线程的存活时间（秒）
        executor.setKeepAliveSeconds(60);

        // Rejection policy: caller runs the task when queue is full
        // 拒绝策略：队列满时由调用方线程执行任务
        executor.setRejectedExecutionHandler(new ThreadPoolExecutor.CallerRunsPolicy());

        executor.initialize();
        return executor;
    }
}
