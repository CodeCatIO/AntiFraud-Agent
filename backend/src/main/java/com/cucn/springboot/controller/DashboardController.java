package com.cucn.springboot.controller;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.cucn.springboot.common.Result;
import com.cucn.springboot.entity.CertRecord;
import com.cucn.springboot.entity.DetectionRecord;
import com.cucn.springboot.entity.User;
import com.cucn.springboot.mapper.CertRecordMapper;
import com.cucn.springboot.mapper.DetectionRecordMapper;
import com.cucn.springboot.utils.TokenUtils;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.*;

import javax.annotation.Resource;
import java.text.SimpleDateFormat;
import java.util.*;

@RestController
@RequestMapping("/dashboard")
public class DashboardController {

    private static final Logger log = LoggerFactory.getLogger(DashboardController.class);

    @Resource
    private DetectionRecordMapper detectionRecordMapper;

    @Resource
    private CertRecordMapper certRecordMapper;

    @GetMapping("/stats")
    public Result getStats() {
        User currentUser = TokenUtils.getCurrentUser();
        if (currentUser == null) return Result.error("401", "请先登录");

        Map<String, Object> stats = new HashMap<>();

        QueryWrapper<DetectionRecord> totalWrapper = new QueryWrapper<>();
        totalWrapper.eq("user_id", currentUser.getId());
        Long totalDetections = detectionRecordMapper.selectCount(totalWrapper);
        stats.put("totalDetections", totalDetections);

        Calendar cal = Calendar.getInstance();
        cal.set(Calendar.HOUR_OF_DAY, 0);
        cal.set(Calendar.MINUTE, 0);
        cal.set(Calendar.SECOND, 0);
        Date todayStart = cal.getTime();

        QueryWrapper<DetectionRecord> todayWrapper = new QueryWrapper<>();
        todayWrapper.eq("user_id", currentUser.getId()).ge("create_time", todayStart);
        Long todayDetections = detectionRecordMapper.selectCount(todayWrapper);
        stats.put("todayDetections", todayDetections);

        QueryWrapper<DetectionRecord> highRiskWrapper = new QueryWrapper<>();
        highRiskWrapper.eq("user_id", currentUser.getId()).eq("risk_level", "高风险");
        Long highRiskCount = detectionRecordMapper.selectCount(highRiskWrapper);
        double highRiskRatio = totalDetections > 0 ? (double) highRiskCount / totalDetections * 100 : 0;
        stats.put("highRiskRatio", Math.round(highRiskRatio * 100) / 100.0);
        stats.put("highRiskCount", highRiskCount);

        Map<String, Long> moduleUsage = new HashMap<>();
        for (String type : Arrays.asList("text", "voice", "image", "composite")) {
            QueryWrapper<DetectionRecord> typeWrapper = new QueryWrapper<>();
            typeWrapper.eq("user_id", currentUser.getId()).eq("type", type);
            moduleUsage.put(type, detectionRecordMapper.selectCount(typeWrapper));
        }
        stats.put("moduleUsage", moduleUsage);

        QueryWrapper<CertRecord> certWrapper = new QueryWrapper<>();
        certWrapper.eq("user_id", currentUser.getId());
        stats.put("totalCerts", certRecordMapper.selectCount(certWrapper));

        QueryWrapper<CertRecord> todayCertWrapper = new QueryWrapper<>();
        todayCertWrapper.eq("user_id", currentUser.getId()).ge("certify_time", todayStart);
        stats.put("todayCerts", certRecordMapper.selectCount(todayCertWrapper));

        return Result.success(stats);
    }

    @GetMapping("/trend")
    public Result getTrend() {
        User currentUser = TokenUtils.getCurrentUser();
        if (currentUser == null) return Result.error("401", "请先登录");

        SimpleDateFormat sdf = new SimpleDateFormat("yyyy-MM-dd");
        List<Map<String, Object>> trendData = new ArrayList<>();
        Calendar cal = Calendar.getInstance();

        for (int i = 6; i >= 0; i--) {
            Calendar dayCal = (Calendar) cal.clone();
            dayCal.add(Calendar.DAY_OF_MONTH, -i);
            Date dayStart = dayCal.getTime();
            dayCal.add(Calendar.DAY_OF_MONTH, 1);
            Date dayEnd = dayCal.getTime();

            Map<String, Object> dayData = new HashMap<>();
            dayData.put("date", sdf.format(dayStart));

            for (String type : Arrays.asList("text", "voice", "image", "composite")) {
                QueryWrapper<DetectionRecord> wrapper = new QueryWrapper<>();
                wrapper.eq("user_id", currentUser.getId()).eq("type", type)
                        .ge("create_time", dayStart).lt("create_time", dayEnd);
                dayData.put(type, detectionRecordMapper.selectCount(wrapper));
            }

            QueryWrapper<DetectionRecord> totalW = new QueryWrapper<>();
            totalW.eq("user_id", currentUser.getId())
                    .ge("create_time", dayStart).lt("create_time", dayEnd);
            dayData.put("total", detectionRecordMapper.selectCount(totalW));

            trendData.add(dayData);
        }
        return Result.success(trendData);
    }

    @GetMapping("/risk-distribution")
    public Result getRiskDistribution() {
        User currentUser = TokenUtils.getCurrentUser();
        if (currentUser == null) return Result.error("401", "请先登录");

        QueryWrapper<DetectionRecord> totalWrapper = new QueryWrapper<>();
        totalWrapper.eq("user_id", currentUser.getId());
        Long totalCount = detectionRecordMapper.selectCount(totalWrapper);

        List<Map<String, Object>> distribution = new ArrayList<>();
        for (String level : Arrays.asList("低风险", "中风险", "高风险")) {
            QueryWrapper<DetectionRecord> wrapper = new QueryWrapper<>();
            wrapper.eq("user_id", currentUser.getId()).eq("risk_level", level);
            Long count = detectionRecordMapper.selectCount(wrapper);

            Map<String, Object> item = new HashMap<>();
            item.put("level", level);
            item.put("count", count);
            double ratio = totalCount > 0 ? (double) count / totalCount * 100 : 0;
            item.put("ratio", Math.round(ratio * 100) / 100.0);
            distribution.add(item);
        }

        Map<String, Object> data = new HashMap<>();
        data.put("totalCount", totalCount);
        data.put("distribution", distribution);
        return Result.success(data);
    }
}
