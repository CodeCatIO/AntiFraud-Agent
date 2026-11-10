package com.cucn.springboot.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.cucn.springboot.entity.Message;

/**
 * @BelongsProject: Software-Cup
 * @BelongsPackage: com.cucn.springboot.service
 * @Author: tengziyan
 * @CreateTime: 2023-07-29  15:45
 * @Description: TODO
 * @Version: 1.0
 */
public interface MessageService extends IService<Message> {

    void  saveMessage(Message message);
    void updateMessage(Message message);
}
