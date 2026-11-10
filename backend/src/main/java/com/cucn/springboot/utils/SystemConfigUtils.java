package com.cucn.springboot.utils;

import lombok.Data;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.annotation.PostConstruct;
import java.io.File;

/**
 * @BelongsProject: Software-Cup
 * @BelongsPackage: com.cucn.springboot.utils
 * @Author: liumei
 * @CreateTime: 2023-10-17  08:23
 * @Description: TODO
 * @Version: 1.0
 */

@Component
@Data
public class SystemConfigUtils {

    @Value("${files.trainFile.path}")
    private String trainFilePath;

    @Value("${files.predictFile.path}")
    private String predictFilePath;

    @Value("${server.ip}")
    private String serverIp;

    @Value("${files.pythonInterpreter.path}")
    private String pythonInterpreter;

    @Value("${files.pythonTrianCode.path}")
    private String pythonTrianCode;

    @Value("${files.pythonPredictCode.path}")
    private String pythonPredictCode;


    @Value("${files.predictModel.path}")
    private String predictModelPath;

    /**
     * Normalize relative paths after properties are injected.
     * Resolution strategy: try the path as-is first; if it does not exist,
     * retry with "../" prefix (parent directory). This makes the same
     * relative default work no matter whether the app is started from
     * the project root (IDEA) or from the backend/ directory (mvn).
     * 注入配置后自动归一化相对路径：先按原路径找，找不到则尝试上级目录，
     * 兼容 IDEA（工作目录=项目根）和 mvn（工作目录=backend/）两种启动方式。
     */
    @PostConstruct
    public void normalizePaths() {
        trainFilePath = resolve(trainFilePath);
        predictFilePath = resolve(predictFilePath);
        pythonTrianCode = resolve(pythonTrianCode);
        pythonPredictCode = resolve(pythonPredictCode);
        predictModelPath = resolve(predictModelPath);
    }

    private String resolve(String path) {
        if (path == null || path.isEmpty() || new File(path).exists()) {
            return path;
        }
        String stripped = path.startsWith("./") ? path.substring(2) : path;
        File parent = new File("../" + stripped);
        if (parent.exists()) {
            return parent.getPath().replace('\\', '/');
        }
        return path;
    }

}
