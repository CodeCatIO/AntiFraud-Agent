package com.cucn.springboot.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.cucn.springboot.common.Result;
import com.cucn.springboot.entity.Message;
import com.cucn.springboot.mapper.MessageMapper;
import com.cucn.springboot.mapper.UserMapper;
import com.cucn.springboot.service.MessageService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.web.bind.annotation.*;

import javax.annotation.Resource;

/**
 * @BelongsProject: Software-Cup
 * @BelongsPackage: com.cucn.springboot.controller
 * @Author: tengziyan
 * @CreateTime: 2023-07-29  15:08
 * @Description: TODO
 * @Version: 1.0
 */
@RestController
@RequestMapping("/message")
public class MessageController {

    @Resource
    private MessageMapper messageMapper;

    @Resource
    private MessageService messageService;
    @Resource
    private UserMapper userMapper;
    @Autowired
    private StringRedisTemplate stringRedisTemplate;

    @PostMapping("/send")
    public Result save(@RequestBody Message message) {
        messageService.saveMessage(message);
        return Result.success();
    }
    @PostMapping("/sendToUpdate")
    public Result update(@RequestBody Message message) {
        messageService.updateMessage(message);
        return Result.success();
    }

    /**
     * 分页查询接口
     * @return
     */
    @GetMapping("/getUserName")
    public Result getUserName() {
        return Result.success(userMapper.selectList(new QueryWrapper<>()));
    }

    @GetMapping("/page")
    public Result findPage(@RequestParam Integer pageNum,
                           @RequestParam Integer pageSize,
                           @RequestParam(defaultValue = "") String sendUserName) {
        QueryWrapper<Message> queryWrapper = new QueryWrapper<>();
        //queryWrapper.eq("is_delete", false);
       // queryWrapper.orderByDesc("id");
        if (!"".equals(sendUserName)) {
            queryWrapper.like("send_user_name", sendUserName);
        }
        return Result.success(messageMapper.selectPage(new Page<>(pageNum, pageSize), queryWrapper));
    }


    @GetMapping("/findById/{id}")
    public Result findById(@PathVariable Integer id) {
        LambdaQueryWrapper<Message> messageLambdaQueryWrapper = new LambdaQueryWrapper<>();
        messageLambdaQueryWrapper.eq(Message::getId,id);
        Message message = messageMapper.selectOne(messageLambdaQueryWrapper);
        return Result.success(message);
    }
    // 设置缓存
    private void setCache(String key, String value) {
        stringRedisTemplate.opsForValue().set(key, value);
    }

    // 删除缓存
    private void flushRedis(String key) {
        stringRedisTemplate.delete(key);
    }


}
