package com.cucn.springboot.utils;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.BufferedReader;
import java.io.InputStreamReader;

/**
 * Utility class for executing Python scripts via ProcessBuilder.
 * This replaces the old PythonUtils class with better error handling,
 * UTF-8 encoding support, and consistent output/error stream reading.
 *
 * 用 ProcessBuilder 执行 Python 脚本的工具类。
 * 替代旧的 PythonUtils 类，提供更好的错误处理、UTF-8 编码支持
 * 和一致的标准输出/错误流读取。
 */
public final class PyProcessExecutor {

    private static final Logger log = LoggerFactory.getLogger(PyProcessExecutor.class);

    private PyProcessExecutor() {
        // Utility class, prevent instantiation
    }

    /**
     * Execute a Python script with the given arguments and wait for completion.
     *
     * 执行一个 Python 脚本并等待完成。
     *
     * @param cmdArray command array: [python_path, script_path, arg1, arg2, ...]
     * @return exit code of the process (0 = success, non-zero = failure)
     * @throws IOException          if an I/O error occurs
     * @throws InterruptedException if the current thread is interrupted
     */
    public static int execute(String[] cmdArray) throws java.io.IOException, InterruptedException {
        log.info("Executing Python command: {}", String.join(" ", cmdArray));

        ProcessBuilder pb = new ProcessBuilder(cmdArray);
        // Force Python to output UTF-8 on Windows
        pb.environment().put("PYTHONIOENCODING", "utf-8");
        pb.redirectErrorStream(false);
        Process process = pb.start();

        // Read stdout
        StringBuilder stdout = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(process.getInputStream(), "UTF-8"))) {
            String line;
            while ((line = reader.readLine()) != null) {
                stdout.append(line).append("\n");
            }
        }
        if (stdout.length() > 0) {
            log.info("Python stdout:\n{}", stdout);
        }

        // Read stderr
        StringBuilder stderr = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(process.getErrorStream(), "UTF-8"))) {
            String line;
            while ((line = reader.readLine()) != null) {
                stderr.append(line).append("\n");
            }
        }
        if (stderr.length() > 0) {
            log.warn("Python stderr:\n{}", stderr);
        }

        int exitCode = process.waitFor();
        if (exitCode != 0) {
            log.error("Python script exited with code {}: {}", exitCode, stderr);
        }
        return exitCode;
    }
}
