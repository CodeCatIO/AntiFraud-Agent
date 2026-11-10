package com.cucn.springboot.controller;

import com.cucn.springboot.client.AiServiceClient;
import com.cucn.springboot.common.Result;
import com.cucn.springboot.entity.User;
import com.cucn.springboot.utils.TokenUtils;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import javax.annotation.Resource;
import java.util.Map;

/**
 * 数据集分类标签可视化
 *
 * 数据由 ai-service 的 scripts/generate_dataset_labels.py 离线生成，
 * 经 Flask /api/dataset/labels 提供，本接口做鉴权透传。
 */
@RestController
@RequestMapping("/dataset")
public class DatasetController {

    @Resource
    private AiServiceClient aiServiceClient;

    @GetMapping("/labels")
    public Result getLabels() {
        User currentUser = TokenUtils.getCurrentUser();
        if (currentUser == null) return Result.error("401", "请先登录");

        Map<String, Object> data = aiServiceClient.getDatasetLabels();
        if (data == null) {
            return Result.error("503", "数据集标签服务不可用，请确认 AI 服务已启动且已运行 generate_dataset_labels.py");
        }
        return Result.success(data);
    }
}
