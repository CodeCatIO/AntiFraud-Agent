package com.cucn.springboot.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.io.Serializable;
import java.util.Date;

@Data
@TableName("agent_run")
public class AgentRunRecord implements Serializable {

    private static final long serialVersionUID = 1L;

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    private String runId;

    private Long caseId;

    private String status;

    private Integer lastEventSeq;

    private String configVersion;

    private String inputHash;

    private String resultJson;

    private String errorCode;

    private Date createdAt;

    private Date updatedAt;

    private Date finishedAt;
}
