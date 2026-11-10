package com.cucn.springboot.controller;

import cn.hutool.core.collection.CollUtil;
import cn.hutool.core.date.DateUtil;
import cn.hutool.core.date.Week;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.cucn.springboot.common.Result;
import com.cucn.springboot.entity.TestFiles;
import com.cucn.springboot.mapper.TestFileMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Date;
import java.util.List;

@RestController
@RequestMapping("/home")
public class IndexController {

    @Autowired
    private TestFileMapper testFileMapper;
    @GetMapping("/members")
    public Result members(){
        int w1=0;
        int w2=0;
        int w3=0;
        int w4=0;
        int w5=0;
        int w6=0;
        int w7=0;
        LambdaQueryWrapper<TestFiles> filesLambdaQueryWrapper = new LambdaQueryWrapper<>();
        List<TestFiles> testFiles = testFileMapper.selectList(filesLambdaQueryWrapper);
        for (TestFiles testFile : testFiles) {
            Date createTime = testFile.getCreateTime();
            Week week = DateUtil.dayOfWeekEnum(createTime);
            switch (week){
                case SUNDAY:w7+=1;break;
                case MONDAY:w1+=1;break;
                case TUESDAY:w2+=1;break;
                case WEDNESDAY:w3+=1;break;
                case THURSDAY:w4+=1;break;
                case FRIDAY:w5+=1;break;
                case SATURDAY:w6+=1;break;
                default:break;
            }
        }
        return Result.success(CollUtil.newArrayList(w1,w2,w3,w4,w5,w6,w7));
    }
}
