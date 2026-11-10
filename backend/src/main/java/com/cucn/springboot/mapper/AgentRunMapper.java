package com.cucn.springboot.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.cucn.springboot.entity.AgentRunRecord;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface AgentRunMapper extends BaseMapper<AgentRunRecord> {
}
