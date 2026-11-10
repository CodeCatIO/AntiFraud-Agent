package com.cucn.springboot.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.cucn.springboot.entity.Message;
import org.apache.ibatis.annotations.Mapper;

/**
 * @BelongsProject: Software-Cup
 * @BelongsPackage: com.cucn.springboot.mapper
 * @Author: tengziyan
 * @CreateTime: 2023-07-29  15:07
 * @Description: TODO
 * @Version: 1.0
 */
@Mapper
public interface MessageMapper extends BaseMapper<Message> {
    int insertSelective(Message record);
}
