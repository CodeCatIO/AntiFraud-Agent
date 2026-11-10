package com.cucn.springboot.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.cucn.springboot.entity.AgentEventRecord;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface AgentEventMapper extends BaseMapper<AgentEventRecord> {
}
