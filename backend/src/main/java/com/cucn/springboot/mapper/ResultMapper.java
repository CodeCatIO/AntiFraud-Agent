package com.cucn.springboot.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.cucn.springboot.entity.OnlineDate;
import org.apache.ibatis.annotations.Mapper;


/**
 * @BelongsProject: Software-Cup
 * @BelongsPackage: com.softcup.springboot.mapper
 * @Author: tengziyan
 * @CreateTime: 2023-07-28  17:32
 * @Description: TODO
 * @Version: 1.0
 */
@Mapper
public interface ResultMapper extends BaseMapper<OnlineDate> {
}
