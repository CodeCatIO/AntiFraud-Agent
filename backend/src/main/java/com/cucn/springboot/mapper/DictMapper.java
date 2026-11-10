package com.cucn.springboot.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.cucn.springboot.entity.Dict;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface DictMapper extends BaseMapper<Dict> {
}
