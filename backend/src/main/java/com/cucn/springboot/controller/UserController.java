package com.cucn.springboot.controller;


import cn.hutool.core.collection.CollUtil;
import cn.hutool.core.util.StrUtil;
import cn.hutool.crypto.SecureUtil;
import cn.hutool.poi.excel.ExcelReader;
import cn.hutool.poi.excel.ExcelUtil;
import cn.hutool.poi.excel.ExcelWriter;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.cucn.springboot.entity.User;
import com.cucn.springboot.service.IRoleService;
import com.cucn.springboot.service.IUserService;
import com.cucn.springboot.common.Constants;
import com.cucn.springboot.utils.TokenUtils;
import com.cucn.springboot.common.Result;
import com.cucn.springboot.controller.dto.UserDTO;
import com.cucn.springboot.controller.dto.UserPasswordDTO;
import com.cucn.springboot.annotation.RateLimit;
import com.cucn.springboot.annotation.OpLog;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import javax.annotation.Resource;
import javax.servlet.ServletOutputStream;
import javax.servlet.http.HttpServletResponse;
import java.io.InputStream;
import java.net.URLEncoder;
import java.util.Date;
import java.util.List;


/**
 * <p>
 *  前端控制器
 * </p>
 *
 * @author 青哥哥
 * @since 2022-01-26
 */
@RestController
@RequestMapping("/user")
public class UserController {

    @Value("${files.upload.path}")
    private String filesUploadPath;
    @Autowired
    private StringRedisTemplate stringRedisTemplate;
    @Resource
    private IUserService userService;
    @Resource
    private IRoleService roleService;
    @PostMapping("/login")
    @RateLimit(key = "login", limit = 10, period = 60, byUser = false)
    @OpLog(module = "user", type = "login", desc = "用户登录")
    public Result login(@RequestBody UserDTO userDTO) {
        String username = userDTO.getUsername();
        String password = userDTO.getPassword();
        if (StrUtil.isBlank(username) || StrUtil.isBlank(password)) {
            return Result.error(Constants.CODE_400, "参数错误");
        }
        UserDTO dto = userService.login(userDTO);
        stringRedisTemplate.opsForValue().set("userId", String.valueOf(dto.getId()));
        return Result.success(dto);
    }

    /**
     * User logout - invalidate the current token
     * 用户登出 - 使当前Token失效
     *
     * Adds the token to Redis blacklist so it can't be used again.
     * 将Token加入Redis黑名单，使其无法再使用。
     *
     * @param token JWT token from request header
     * @return success result
     */
    @PostMapping("/logout")
    public Result logout(@RequestHeader(value = "token", required = false) String token) {
        if (token != null) {
            TokenUtils.invalidateToken(token);
        }
        return Result.success("登出成功 Logged out successfully");
    }
    private void setCache(String key, String value) {
        stringRedisTemplate.opsForValue().set(key, value);
    }
    @PostMapping("/register")
    @RateLimit(key = "register", limit = 5, period = 3600, byUser = false)
    @OpLog(module = "user", type = "register", desc = "用户注册")
    public Result register(@RequestBody UserDTO userDTO) {
        String username = userDTO.getUsername();
        String password = userDTO.getPassword();
        if (StrUtil.isBlank(username) || StrUtil.isBlank(password)) {
            return Result.error(Constants.CODE_400, "参数错误");
        }
        return Result.success(userService.register(userDTO));
    }
    // 新增或者更新
    @PostMapping("/saveUpdateUser")
    public Result saveUpdateUser(@RequestBody User user) {
        userService.saveUpdateUser(user);
        return Result.success();
    }


    /**
     * Change password
     * 修改密码
     * @param userPasswordDTO contains old password and new password
     * @return success result
     */
    @PostMapping("/password")
    public Result password(@RequestBody UserPasswordDTO userPasswordDTO) {
        // Password verification and encoding are handled in service layer
        // 密码验证和加密在 Service 层处理
        userService.updatePassword(userPasswordDTO);
        return Result.success();
    }

    @DeleteMapping("/{id}")
    public Result delete(@PathVariable Integer id) {
        return Result.success(userService.removeById(id));
    }

    @PostMapping("/del/batch")
    public Result deleteBatch(@RequestBody List<Integer> ids) {
        return Result.success(userService.removeByIds(ids));
    }

    @GetMapping
    public Result findAll() {
        return Result.success(userService.list());
    }

    @GetMapping("/role/{role}")
    public Result findUsersByRole(@PathVariable String role) {
        QueryWrapper<User> queryWrapper = new QueryWrapper<>();
        queryWrapper.eq("role", role);
        List<User> list = userService.list(queryWrapper);
        return Result.success(list);
    }

    @GetMapping("/{id}")
    public Result findOne(@PathVariable Integer id) {
        return Result.success(userService.getById(id));
    }

    @GetMapping("/username/{username}")
    public Result findByUsername(@PathVariable String username) {
        QueryWrapper<User> queryWrapper = new QueryWrapper<>();
        queryWrapper.eq("username", username);
        return Result.success(userService.getOne(queryWrapper));
    }

    @GetMapping("/page")
    public Result findPage(@RequestParam Integer pageNum,
                               @RequestParam Integer pageSize,
                               @RequestParam(defaultValue = "") String username,
                               @RequestParam(defaultValue = "") String email,
                               @RequestParam(defaultValue = "") String address) {

//        QueryWrapper<User> queryWrapper = new QueryWrapper<>();
//        queryWrapper.orderByDesc("id");
//        if (!"".equals(username)) {
//            queryWrapper.like("username", username);
//        }
//        if (!"".equals(email)) {
//            queryWrapper.like("email", email);
//        }
//        if (!"".equals(address)) {
//            queryWrapper.like("address", address);
//        }
        return Result.success(userService.findPage(new Page<>(pageNum, pageSize), username, email, address));
    }


    @GetMapping("/getUserName")
    public Result getUserName() {
        return Result.success(userService.list());
    }
    @GetMapping("/totle")
    public Result totle() {
        List<User> list = userService.list();
        for (User user : list) {
            Date createTime = user.getCreateTime();

        }
        return Result.success(list.size());
    }
    /**
     * 导出接口
     */
    @GetMapping("/export")
    public void export(HttpServletResponse response) throws Exception {
        // 从数据库查询出所有的数据
        List<User> list = userService.list();
        // 导出前清空密码哈希，避免凭据外泄
        // Strip password hashes before exporting
        list.forEach(u -> u.setPassword(null));
        // 通过工具类创建writer 写出到磁盘路径
//        ExcelWriter writer = ExcelUtil.getWriter(filesUploadPath + "/用户信息.xlsx");
        // 在内存操作，写出到浏览器
        ExcelWriter writer = ExcelUtil.getWriter(true);
        //自定义标题别名
        writer.addHeaderAlias("username", "用户名");
        writer.addHeaderAlias("nickname", "昵称");
        writer.addHeaderAlias("email", "邮箱");
        writer.addHeaderAlias("phone", "电话");
        writer.addHeaderAlias("address", "地址");
        writer.addHeaderAlias("createTime", "创建时间");
        writer.addHeaderAlias("avatarUrl", "头像");

        // 一次性写出list内的对象到excel，使用默认样式，强制输出标题
        writer.write(list, true);

        // 设置浏览器响应的格式
        response.setContentType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;charset=utf-8");
        String fileName = URLEncoder.encode("用户信息", "UTF-8");
        response.setHeader("Content-Disposition", "attachment;filename=" + fileName + ".xlsx");

        ServletOutputStream out = response.getOutputStream();
        writer.flush(out, true);
        out.close();
        writer.close();

    }

    /**
     * excel 导入
     * @param file
     * @throws Exception
     */
    @PostMapping("/import")
    public Result imp(MultipartFile file) throws Exception {
        InputStream inputStream = file.getInputStream();
        ExcelReader reader = ExcelUtil.getReader(inputStream);
        // 方式1：(推荐) 通过 javabean的方式读取Excel内的对象，但是要求表头必须是英文，跟javabean的属性要对应起来
//        List<User> list = reader.readAll(User.class);

        // 方式2：忽略表头的中文，直接读取表的内容
        List<List<Object>> list = reader.read(1);
        List<User> users = CollUtil.newArrayList();
        for (List<Object> row : list) {
            User user = new User();
            user.setUsername(row.get(0).toString());
            user.setPassword(row.get(1).toString());
            user.setNickname(row.get(2).toString());
            user.setEmail(row.get(3).toString());
            user.setPhone(row.get(4).toString());
            user.setAddress(row.get(5).toString());
            user.setAvatarUrl(row.get(6).toString());
            users.add(user);
        }

        userService.saveBatch(users);
        return Result.success(true);
    }

}

