package com.cucn.springboot.controller.dto;

import com.cucn.springboot.entity.Menu;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

import java.util.List;

/**
 * 接受前端登录请求的参数
 */
@Data
public class UserDTO {
    private Integer id;
    private String username;
    // 只允许写入（登录/注册请求体），响应中不输出密码
    // Write-only: password is accepted in requests but never returned in responses
    @JsonProperty(access = JsonProperty.Access.WRITE_ONLY)
    private String password;
    private String nickname;
    private String avatarUrl;
    private String token;
    private String role;
    private Integer roleid;
    private List<Menu> menus;
}
