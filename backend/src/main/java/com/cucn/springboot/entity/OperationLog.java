package com.cucn.springboot.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.Data;

import java.io.Serializable;
import java.util.Date;

/**
 * Operation Log Entity
 * 操作日志实体类
 *
 * Records user operations for audit and security monitoring purposes.
 * 记录用户操作，用于审计和安全监控。
 */
@Data
@TableName("sys_operation_log")
public class OperationLog implements Serializable {

    private static final long serialVersionUID = 1L;

    @TableId(value = "id", type = IdType.AUTO)
    private Integer id;

    /** User ID of the operator 操作人ID */
    private Integer userId;

    /** Username of the operator 操作人用户名 */
    private String username;

    /** Operation module 操作模块 e.g. user, detect, system */
    private String module;

    /** Operation type 操作类型 e.g. login, create, update, delete, query */
    private String type;

    /** Operation description 操作描述 */
    private String description;

    /** Request method 请求方式 GET/POST/PUT/DELETE */
    private String method;

    /** Request URL 请求URL */
    private String url;

    /** Client IP 客户端IP */
    private String ip;

    /** Request parameters (JSON) 请求参数（JSON格式） */
    private String params;

    /** Result: success/fail 操作结果：成功/失败 */
    private String result;

    /** Error message (if failed) 错误信息（失败时） */
    private String errorMsg;

    /** Execution time in ms 执行耗时（毫秒） */
    private Long costTime;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss", timezone = "GMT+8")
    private Date createTime;
}
