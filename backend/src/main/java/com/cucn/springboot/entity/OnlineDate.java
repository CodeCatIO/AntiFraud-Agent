package com.cucn.springboot.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.fasterxml.jackson.annotation.JsonFormat;
import io.swagger.annotations.ApiModelProperty;
import lombok.Data;

import java.util.Date;

@Data
@TableName("sys_result")
public class OnlineDate {
    @TableId(type = IdType.AUTO)
    private Integer id;
    /**
     * 测试集中的index
     */
    private Integer testid;
    private Integer result;
    @ApiModelProperty("创建时间")
    @JsonFormat(pattern="yyyy-MM-dd HH:mm:ss")
    private Date createTime;
    @TableField("testfile_id")
    private Integer testfileid;
    @TableField("text")
    private String text;
}
