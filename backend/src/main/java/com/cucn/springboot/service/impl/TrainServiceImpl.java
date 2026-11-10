package com.cucn.springboot.service.impl;

import cn.hutool.core.io.FileUtil;
import cn.hutool.crypto.SecureUtil;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.cucn.springboot.entity.Files;
import com.cucn.springboot.mapper.FileMapper;
import com.cucn.springboot.utils.FileUtils;
import com.cucn.springboot.utils.PyProcessExecutor;
import com.cucn.springboot.utils.SystemConfigUtils;
import com.cucn.springboot.common.Result;
import com.cucn.springboot.service.ITrainService;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.util.ObjectUtils;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.multipart.MultipartFile;

import javax.annotation.Resource;
import javax.servlet.http.HttpServletResponse;
import java.io.File;
import java.io.IOException;
import java.util.UUID;


/**
 * @BelongsProject: Software-Cup
 * @BelongsPackage: com.cucn.springboot.service.impl
 * @Author: liumei
 * @CreateTime: 2023-10-14  16:00
 * @Description: TODO
 * @Version: 1.0
 */

@Service
public class TrainServiceImpl  implements ITrainService {


    @Resource
    private SystemConfigUtils config;

    @Resource
    private FileMapper fileMapper;

    @Autowired
    private StringRedisTemplate stringRedisTemplate;

    public Logger logger = LoggerFactory.getLogger(TrainServiceImpl.class);

    /**
     * 保存上传文件（比如上传训练集）
     *  error  warning  info debug
     * step1:读取基本信息
     * step2：写文件
     * step3: 将数据写入trainfile文件
     * @param file
     * @return
     */
    @Override
    public boolean uploadTrainFile(MultipartFile file) throws Exception {

        logger.info("#######################开始将训练集文件写入#################");


        String trianFileName = FileUtils.writeFile( config.getTrainFilePath(),file);

        Files saveFileRecord = buildTrainFile(file, trianFileName);
        fileMapper.insert(saveFileRecord);

        return true;
    }

    /**
     * 封装入库的
     * @param file
     * @param trianFileName
     * @return
     */
    private Files buildTrainFile(MultipartFile file,  String trianFileName) throws IOException {
        long size = file.getSize();
        // 存储数据库
        Files trainFileRecord = new Files();
        trainFileRecord.setName(file.getOriginalFilename());
        String type = FileUtil.extName(file.getOriginalFilename());
        trainFileRecord.setType(type);
        // 单位 kb
        trainFileRecord.setSize(size / 1024);
        //1.9090应该存放到配置文件中 2.url返回给前端用下载的训练用的url，可以将名字改成modelDownLoadUrl
        String serverIp = config.getServerIp();
        String url = "http://" + serverIp + ":9090/python/" + trianFileName;
        trainFileRecord.setUrl(url);

        // 获取文件的md5，用于校验文件数据是否被删除或改动
       // String md5 = SecureUtil.md5(file.getInputStream());
        trainFileRecord.setMd5(null);
        //获取当前用户的user_id
        String userId = stringRedisTemplate.opsForValue().get("userId");
        trainFileRecord.setUserid(Integer.parseInt(userId));
        return trainFileRecord;
    }

    /**
     * 训练
     * @param url  训练模型的名字
     * @return
     */
    @Override
    public Result train(String url,String trainModel) throws IOException {
        // 查询是否已经完成训练
        LambdaQueryWrapper<Files> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.eq(Files::getUrl, "http://localhost:9090/python/" + url);
        Files files = fileMapper.selectOne(queryWrapper);

        if (!ObjectUtils.isEmpty(files.getPythonurl())) {
            return Result.error("505", "已完成，请下载");
        }

        //读取文件开始训练
        String trainModelFileName = url.replace("csv", ".h5");

        try {
            String[] arguments = new String[] {config.getPythonInterpreter(),
                    config.getPythonTrianCode(),
                    config.getTrainFilePath()+url,
                    config.getTrainFilePath()+trainModelFileName,
                    trainModel
            };

            int i = PyProcessExecutor.execute(arguments);

            if (i == 1) {
                return Result.error("507", "训练失败");
            }

        } catch (InterruptedException e) {
            throw new RuntimeException(e);
        }

        files.setPythonurl(trainModelFileName);
        files.setTrainModel(trainModel);
        fileMapper.updateById(files);

        return Result.success();
    }

    @Override
    public void updateById(Files files) {
        fileMapper.updateById(files);
    }

    @Override
    public void downloadTrainFile( String pythonUrl, HttpServletResponse response) throws IOException {
        FileUtils.downloadResultFile(pythonUrl,config.getTrainFilePath(),response);
    }

}
