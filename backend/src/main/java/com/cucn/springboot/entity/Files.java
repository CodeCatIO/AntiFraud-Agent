package com.cucn.springboot.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import io.swagger.annotations.ApiModelProperty;
import lombok.Data;

import java.util.Date;

@Data
@TableName("sys_trainfile")
public class Files {

    @TableId(type = IdType.AUTO)
    private Integer id;
    private String name;
    private String type;
    private Long size;
    //下载链接
    private String url;
    private String pythonurl;
    private String md5;
    private Boolean isDelete;
    private Boolean enable;
    @ApiModelProperty("创建时间")
    private Date createTime;
    @TableField("user_id")
    private int userid;
    private String trainModel;
}
