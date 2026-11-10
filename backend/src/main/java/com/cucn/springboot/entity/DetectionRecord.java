package com.cucn.springboot.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.Data;

import java.io.Serializable;
import java.util.Date;

/**
 * 检测记录实体
 */
@Data
@TableName("detection_record")
public class DetectionRecord implements Serializable {

    private static final long serialVersionUID = 1L;

    @TableId(value = "id", type = IdType.AUTO)
    private Integer id;

    private Integer userId;

    /** 检测类型：text/voice/image/composite */
    private String type;

    private String inputContent;

    /** 风险分数 0-100 */
    private Integer riskScore;

    /** 风险等级：低风险/中风险/高风险 */
    private String riskLevel;

    /** JSON格式详细结果 */
    private String detail;

    /**
     * Task status: pending/processing/completed/failed
     * 任务状态：待处理/处理中/已完成/失败
     * Used for async detection tasks. For sync tasks, default is "completed".
     * 用于异步检测任务。同步任务默认为"completed"。
     */
    private String status;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss", timezone = "GMT+8")
    private Date createTime;
}
