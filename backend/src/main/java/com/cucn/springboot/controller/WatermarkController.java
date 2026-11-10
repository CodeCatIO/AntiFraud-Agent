package com.cucn.springboot.controller;

import cn.hutool.core.util.StrUtil;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.cucn.springboot.common.Result;
import com.cucn.springboot.entity.User;
import com.cucn.springboot.utils.TokenUtils;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.BufferedReader;
import java.io.File;
import java.io.InputStreamReader;
import java.util.*;

@RestController
@RequestMapping("/watermark")
public class WatermarkController {

    private static final Logger log = LoggerFactory.getLogger(WatermarkController.class);

    @Value("${files.upload.path}")
    private String fileUploadPath;

    @Value("${files.python.path:python/}")
    private String pythonScriptPath;

    @Value("${files.python.executable:python}")
    private String pythonExecutable;

    private final ObjectMapper objectMapper = new ObjectMapper();

    @PostMapping("/embed")
    public Result embedWatermark(@RequestParam MultipartFile file,
                                  @RequestParam String watermarkText) {
        if (file.isEmpty()) return Result.error("400", "请上传图片文件");
        if (StrUtil.isBlank(watermarkText)) return Result.error("400", "水印文本不能为空");
        User currentUser = TokenUtils.getCurrentUser();
        if (currentUser == null) return Result.error("401", "请先登录");
        try {
            String originalFilename = file.getOriginalFilename();
            String fileSuffix = originalFilename != null && originalFilename.contains(".")
                    ? originalFilename.substring(originalFilename.lastIndexOf(".")) : ".png";
            String savedFileName = UUID.randomUUID().toString().replace("-", "") + fileSuffix;
            String uploadDir = fileUploadPath + "watermark/";
            File uploadDirFile = new File(uploadDir);
            if (!uploadDirFile.exists()) uploadDirFile.mkdirs();
            String inputPath = uploadDir + savedFileName;
            file.transferTo(new File(inputPath));

            String outputFileName = "wm_" + savedFileName;
            String outputPath = uploadDir + outputFileName;

            String scriptPath = pythonScriptPath + "watermark.py";
            String[] cmd = {pythonExecutable, scriptPath, "embed", inputPath, outputPath, watermarkText};
            String output = executePython(cmd);
            JsonNode resultNode = objectMapper.readTree(output);

            Map<String, Object> data = new HashMap<>();
            data.put("outputPath", outputPath);
            data.put("outputFileName", outputFileName);
            if (resultNode.has("success")) data.put("success", resultNode.get("success").asBoolean());
            return Result.success(data);
        } catch (Exception e) {
            log.error("水印嵌入失败", e);
            return Result.error("500", "水印嵌入失败：" + e.getMessage());
        }
    }

    @PostMapping("/extract")
    public Result extractWatermark(@RequestParam MultipartFile file) {
        if (file.isEmpty()) return Result.error("400", "请上传图片文件");
        User currentUser = TokenUtils.getCurrentUser();
        if (currentUser == null) return Result.error("401", "请先登录");
        try {
            String originalFilename = file.getOriginalFilename();
            String fileSuffix = originalFilename != null && originalFilename.contains(".")
                    ? originalFilename.substring(originalFilename.lastIndexOf(".")) : ".png";
            String savedFileName = UUID.randomUUID().toString().replace("-", "") + fileSuffix;
            String uploadDir = fileUploadPath + "watermark/";
            File uploadDirFile = new File(uploadDir);
            if (!uploadDirFile.exists()) uploadDirFile.mkdirs();
            String filePath = uploadDir + savedFileName;
            file.transferTo(new File(filePath));

            String scriptPath = pythonScriptPath + "watermark.py";
            String[] cmd = {pythonExecutable, scriptPath, "extract", filePath};
            String output = executePython(cmd);
            JsonNode resultNode = objectMapper.readTree(output);

            Map<String, Object> data = new HashMap<>();
            if (resultNode.has("watermarkText")) data.put("watermarkText", resultNode.get("watermarkText").asText());
            if (resultNode.has("success")) data.put("success", resultNode.get("success").asBoolean());
            data.put("result", objectMapper.readValue(output, Map.class));
            return Result.success(data);
        } catch (Exception e) {
            log.error("水印提取失败", e);
            return Result.error("500", "水印提取失败：" + e.getMessage());
        }
    }

    private String executePython(String[] cmd) throws Exception {
        log.info("执行Python命令：{}", String.join(" ", cmd));
        Process process = Runtime.getRuntime().exec(cmd);
        BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream(), "UTF-8"));
        StringBuilder output = new StringBuilder();
        String line;
        while ((line = reader.readLine()) != null) output.append(line);
        BufferedReader errorReader = new BufferedReader(new InputStreamReader(process.getErrorStream(), "UTF-8"));
        StringBuilder errorOutput = new StringBuilder();
        while ((line = errorReader.readLine()) != null) errorOutput.append(line).append("\n");
        int exitCode = process.waitFor();
        if (exitCode != 0) throw new RuntimeException("Python脚本执行失败：" + errorOutput);
        return output.toString();
    }
}
