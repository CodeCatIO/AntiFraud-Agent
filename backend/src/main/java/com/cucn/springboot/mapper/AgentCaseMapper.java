package com.cucn.springboot.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.cucn.springboot.entity.AgentCaseRecord;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface AgentCaseMapper extends BaseMapper<AgentCaseRecord> {
}
