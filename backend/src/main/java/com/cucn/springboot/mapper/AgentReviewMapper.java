package com.cucn.springboot.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.cucn.springboot.entity.AgentReviewRecord;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface AgentReviewMapper extends BaseMapper<AgentReviewRecord> {
}
