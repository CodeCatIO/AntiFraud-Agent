package com.cucn.springboot.controller;

import cn.hutool.core.util.StrUtil;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.cucn.springboot.common.Result;
import com.cucn.springboot.entity.CertRecord;
import com.cucn.springboot.entity.User;
import com.cucn.springboot.mapper.CertRecordMapper;
import com.cucn.springboot.utils.TokenUtils;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.*;

import javax.annotation.Resource;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.util.*;

@RestController
@RequestMapping("/blockchain")
public class BlockchainController {

    private static final Logger log = LoggerFactory.getLogger(BlockchainController.class);

    @Resource
    private CertRecordMapper certRecordMapper;

    @Value("${files.python.path:python/}")
    private String pythonScriptPath;

    @Value("${files.python.executable:python}")
    private String pythonExecutable;

    private final ObjectMapper objectMapper = new ObjectMapper();

    @PostMapping("/certify")
    public Result certify(@RequestBody Map<String, String> params) {
        String content = params.get("content");
        if (StrUtil.isBlank(content)) return Result.error("400", "存证内容不能为空");
        User currentUser = TokenUtils.getCurrentUser();
        if (currentUser == null) return Result.error("401", "请先登录");
        try {
            String scriptPath = pythonScriptPath + "blockchain_cert.py";
            String[] cmd = {pythonExecutable, scriptPath, "certify", content};
            String output = executePython(cmd);
            JsonNode resultNode = objectMapper.readTree(output);
            String contentHash = resultNode.has("hash") ? resultNode.get("hash").asText() : "";
            int blockIndex = resultNode.has("blockIndex") ? resultNode.get("blockIndex").asInt() : 0;

            CertRecord record = new CertRecord();
            record.setUserId(currentUser.getId());
            record.setContentHash(contentHash);
            record.setBlockIndex(blockIndex);
            record.setCertifyTime(new Date());
            record.setContent(content.length() > 200 ? content.substring(0, 200) : content);
            certRecordMapper.insert(record);

            Map<String, Object> data = new HashMap<>();
            data.put("recordId", record.getId());
            data.put("contentHash", contentHash);
            data.put("blockIndex", blockIndex);
            data.put("certifyTime", record.getCertifyTime());
            return Result.success(data);
        } catch (Exception e) {
            log.error("区块链存证失败", e);
            return Result.error("500", "区块链存证失败：" + e.getMessage());
        }
    }

    @PostMapping("/verify")
    public Result verify(@RequestBody Map<String, String> params) {
        String hash = params.get("hash");
        String content = params.get("content");
        if (StrUtil.isBlank(hash) && StrUtil.isBlank(content)) return Result.error("400", "请提供哈希值或存证内容");
        User currentUser = TokenUtils.getCurrentUser();
        if (currentUser == null) return Result.error("401", "请先登录");
        try {
            String scriptPath = pythonScriptPath + "blockchain_cert.py";
            String[] cmd;
            if (StrUtil.isNotBlank(hash)) {
                cmd = new String[]{pythonExecutable, scriptPath, "verify", "hash", hash};
            } else {
                cmd = new String[]{pythonExecutable, scriptPath, "verify", "content", content};
            }
            String output = executePython(cmd);
            JsonNode resultNode = objectMapper.readTree(output);
            boolean valid = resultNode.has("valid") && resultNode.get("valid").asBoolean();

            Map<String, Object> data = new HashMap<>();
            data.put("valid", valid);
            data.put("detail", objectMapper.readValue(output, Map.class));
            return Result.success(data);
        } catch (Exception e) {
            log.error("区块链验证失败", e);
            return Result.error("500", "区块链验证失败：" + e.getMessage());
        }
    }

    @GetMapping("/records")
    public Result getRecords(
            @RequestParam(defaultValue = "1") Integer pageNum,
            @RequestParam(defaultValue = "10") Integer pageSize) {
        User currentUser = TokenUtils.getCurrentUser();
        if (currentUser == null) return Result.error("401", "请先登录");
        Page<CertRecord> page = new Page<>(pageNum, pageSize);
        QueryWrapper<CertRecord> queryWrapper = new QueryWrapper<>();
        queryWrapper.eq("user_id", currentUser.getId());
        queryWrapper.orderByDesc("certify_time");
        Page<CertRecord> resultPage = certRecordMapper.selectPage(page, queryWrapper);
        return Result.success(resultPage);
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
