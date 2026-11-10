package com.cucn.springboot.controller;

import cn.hutool.core.date.DateUtil;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.cucn.springboot.entity.OnlineDate;
import com.cucn.springboot.common.Result;
import com.cucn.springboot.mapper.ResultMapper;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import javax.annotation.Resource;
import java.util.*;

@RestController
@RequestMapping("/echarts")
public class EchartsController {


    @Resource
    private ResultMapper resultMapper;


    @GetMapping("/members")
    public Result members() {
        ArrayList<Long> integers = new ArrayList<>();
        for (int i = 0; i < 6; i++) {
            LambdaQueryWrapper<OnlineDate> dateLambdaQueryWrapper = new LambdaQueryWrapper<>();
            dateLambdaQueryWrapper.eq(OnlineDate::getResult, i);
            Long aLong = resultMapper.selectCount(dateLambdaQueryWrapper);
            integers.add(aLong);
        }
        return Result.success(integers);
    }
    @GetMapping("/index")
    public Result index() {
        Map<Integer,List> map = new HashMap<>();
        for (int i = 0; i < 2; i++) {
            LambdaQueryWrapper<OnlineDate> dateLambdaQueryWrapper = new LambdaQueryWrapper<>();
            dateLambdaQueryWrapper.eq(OnlineDate::getResult, i);
            List<OnlineDate> dates = resultMapper.selectList(dateLambdaQueryWrapper);
            map.put(i,dates);
        }
        return Result.success(map);
    }
    @GetMapping("/totle")
    public Result totle() {
        LambdaQueryWrapper<OnlineDate> dateLambdaQueryWrapper = new LambdaQueryWrapper<>();
        Long aLong = resultMapper.selectCount(dateLambdaQueryWrapper);
        return Result.success(aLong);
    }

    @GetMapping("/totle1")
    public Result totle1() {
        List<OnlineDate> onlineDates = resultMapper.selectList(new QueryWrapper<OnlineDate>());
        String today = DateUtil.today();
        Integer totle=0;
        for (OnlineDate onlineDate : onlineDates) {
            Date createTime = onlineDate.getCreateTime();
            String format = DateUtil.format(createTime, "yyyy-MM-dd");
            if (format.equals(today)){
                totle++;
            }
        }
        return Result.success(totle);
    }
    @GetMapping("/totle3")
    public Result totle3() {
        Long max=0l;
        Map<Integer,Long> map = new HashMap<>();
        for (int i = 0; i < 2; i++) {
            LambdaQueryWrapper<OnlineDate> dateLambdaQueryWrapper = new LambdaQueryWrapper<>();
            dateLambdaQueryWrapper.eq(OnlineDate::getResult, i);
            Long aLong = resultMapper.selectCount(dateLambdaQueryWrapper);
            map.put(i,aLong);
        }
        Integer maxKey = null;
        for (Integer key : map.keySet()) {
            if (maxKey == null || map.get(key) > map.get(maxKey)) {
                maxKey = key;
            }
        }
        System.out.println(maxKey);
        return Result.success(map.get(maxKey));
    }
//    @GetMapping("/Max")
//    public Result Max() {
//        List<Long> integers = new ArrayList<>();
//        for (int i = 0; i < 6; i++) {
//            LambdaQueryWrapper<OnlineDate> dateLambdaQueryWrapper = new LambdaQueryWrapper<>();
//            dateLambdaQueryWrapper.eq(OnlineDate::getResult, i);
//            Long aLong = resultMapper.selectCount(dateLambdaQueryWrapper);
//            integers.add(aLong);
//        }
//        Integer max = Collections.max(integers).intValue();
//
//        return Result.success(max+300);
//    }
}
