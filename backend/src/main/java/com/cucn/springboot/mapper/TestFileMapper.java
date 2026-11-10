package com.cucn.springboot.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.cucn.springboot.entity.TestFiles;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface TestFileMapper extends BaseMapper<TestFiles> {
}
