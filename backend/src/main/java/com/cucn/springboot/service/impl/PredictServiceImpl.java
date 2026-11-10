package com.cucn.springboot.service.impl;

import cn.hutool.core.date.DateUtil;
import cn.hutool.core.io.FileUtil;
import cn.hutool.core.util.ObjectUtil;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.cucn.springboot.common.Constants;
import com.cucn.springboot.common.Result;
import com.cucn.springboot.entity.OnlineDate;
import com.cucn.springboot.entity.TestFiles;
import com.cucn.springboot.mapper.ResultMapper;
import com.cucn.springboot.mapper.TestFileMapper;
import com.cucn.springboot.service.IPredictService;
import com.cucn.springboot.utils.FileUtils;
import com.cucn.springboot.utils.JsonUtils;
import com.cucn.springboot.utils.PyProcessExecutor;
import com.cucn.springboot.utils.SystemConfigUtils;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import javax.annotation.Resource;
import javax.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.*;

/**
 * @BelongsProject: Software-Cup
 * @BelongsPackage: com.cucn.springboot.service.impl
 * @Author: liumei
 * @CreateTime: 2023-10-18  16:24
 * @Description: TODO
 * @Version: 1.0
 */
@Service
public class PredictServiceImpl  implements IPredictService {

    @Resource
    private SystemConfigUtils config;

    @Autowired
    private StringRedisTemplate stringRedisTemplate;

    public Logger logger = LoggerFactory.getLogger(PredictServiceImpl.class);

    @Resource
    private TestFileMapper testFileMapper;

    @Resource
    private ResultMapper resultMapper;


    @Override
    public boolean uploadPredictFile(MultipartFile file) throws Exception {

        logger.info("#######################开始将预测集文件写入#################");
        String fileName = FileUtils.writeFile(config.getPredictFilePath(),file);

        testFileMapper.insert(buildPredictFile(file, fileName));

        flushRedis(Constants.FILES_KEY);
        return true;
    }

    @Override
    public Result beginPredict(String url) throws IOException {
        // 执行时间（1s）
        TestFiles testFiles = selectTestFilesByUrl(url);
        if (!ObjectUtil.isEmpty(testFiles.getEnable())){
            return Result.error("505","已完成，请查看结果");
        }

        //读取文件开始训练
        String predictResultFileName = url.replace("csv", "json");

        try {

            String[] arguments = new String[] {config.getPythonInterpreter(),
                    config.getPythonPredictCode(),
                    config.getPredictFilePath()+url,
                    config.getPredictFilePath()+predictResultFileName,
                    config.getPredictModelPath()
            };

            int i = PyProcessExecutor.execute(arguments);

            if (i == 1) {
                return Result.error("507", "训练失败");
            }

        } catch (Exception e) {
            throw new RuntimeException(e);
        }

        System.out.println("预测成功");
        testFiles.setEnable("1");
        testFiles.setJsonUrl(predictResultFileName);
        testFileMapper.updateById(testFiles);

        //读取json，解析
      HashMap<String,String> resultMap = (HashMap<String, String>) JsonUtils.readJsonFile
              (config.getPredictFilePath()+predictResultFileName);
        //将本次结果入库 sys_result
        int i=0;
        for (Map.Entry < String,String > entry: resultMap.entrySet()) {
            OnlineDate record = new OnlineDate();
            record.setCreateTime(new Date());
            record.setTestfileid(testFiles.getId());
            record.setText(entry.getKey());
            record.setTestid(i++);
            String value = entry.getValue();
            if(value.equals("负面"))
            {
                record.setResult(1);
            }
            else
            {
                record.setResult(0);
            }
            try {
                resultMapper.insert(record);
            }
            catch (Exception e)
            {

            }

        }



        flushRedis(Constants.FILES_KEY);
        return Result.success();
    }

    @Override
    public IPage<TestFiles> findPage(Integer pageNum, Integer pageSize, String name) {
        QueryWrapper<TestFiles> queryWrapper = new QueryWrapper<>();

        // 查询未删除的记录
        queryWrapper.eq("is_delete", false);
        queryWrapper.orderByDesc("id");
        if (!"".equals(name)) {
            queryWrapper.like("name", name);
        }

       IPage<TestFiles> result = testFileMapper.selectPage(new Page<>(pageNum, pageSize), queryWrapper);
        return result;
    }



    private TestFiles selectTestFilesByUrl(String url) {
        LambdaQueryWrapper<TestFiles> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.eq(TestFiles::getUrl,"http://localhost:9090/DataTest/"+url);
        return testFileMapper.selectOne(queryWrapper);
    }

    private TestFiles buildPredictFile(MultipartFile file, String fileName) throws IOException {

        String originalFilename = file.getOriginalFilename();
        String type = FileUtil.extName(originalFilename);
        long size = file.getSize();
        // 获取文件的md5
        String md5 = null;//SecureUtil.md5(file.getInputStream());

        String url = "http://" + config.getServerIp() + ":9090/DataTest/" + fileName;
        //获取当前用户的user_id
        String userId = stringRedisTemplate.opsForValue().get("userId");

        System.out.println("----------------------------------"+userId);
        // 存储数据库
        TestFiles saveFile = new TestFiles();
        saveFile.setName(originalFilename);
        saveFile.setType(type);
        saveFile.setSize(size/1024); // 单位 kb
        saveFile.setUrl(url);
        saveFile.setMd5(md5);
        saveFile.setUserid(Integer.parseInt(userId));

        return saveFile;

    }


    // 设置缓存
    private void setCache(String key, String value) {
        stringRedisTemplate.opsForValue().set(key, value);
    }

    // 删除缓存
    private void flushRedis(String key) {
        stringRedisTemplate.delete(key);
    }

    @Override
    public boolean deletePredictData(Integer id) {

        LambdaQueryWrapper<OnlineDate> onlineDateLambdaQueryWrapper = new LambdaQueryWrapper<>();
        onlineDateLambdaQueryWrapper.eq(OnlineDate::getTestfileid,id);
        resultMapper.delete(onlineDateLambdaQueryWrapper);
        testFileMapper.deleteById(id);
        flushRedis(Constants.FILES_KEY);
        return true;
    }

    @Override
    public boolean deleteBatch(List<Integer> ids) {

        QueryWrapper<OnlineDate> onlineDateQueryWrapper = new QueryWrapper<>();
        onlineDateQueryWrapper.in("testfile_id",ids);
        List<OnlineDate> onlinedates = resultMapper.selectList(onlineDateQueryWrapper);
        for (OnlineDate onlinedate:onlinedates){
            resultMapper.deleteById(onlinedate);
        }
        // select * from sys_file where id in (id,id,id...)
        QueryWrapper<TestFiles> queryWrapper = new QueryWrapper<>();
        queryWrapper.in("id", ids);
        List<TestFiles> testfiles = testFileMapper.selectList(queryWrapper);
        for (TestFiles file : testfiles) {
            testFileMapper.deleteById(file);
        }
        return true;
    }

    @Override
    public TestFiles getById(Integer id) {

        return testFileMapper.selectById(id);
    }

    @Override
    public Integer predictTotle() {

        List<TestFiles> testfiles = testFileMapper.selectList(new QueryWrapper<TestFiles>());
        String today = DateUtil.today();
        Integer totle=0;
        for (TestFiles file : testfiles) {
            Date createTime = file.getCreateTime();
            String format = DateUtil.format(createTime, "yyyy-MM-dd");
            if (format.equals(today)){
                totle++;
            }
        }
        return totle;
    }

    @Override
    public  ArrayList<Long> getMalfunctionCount(Integer id) {

        ArrayList<Long> integers = new ArrayList<>();
        for (int i = 0; i < 6; i++) {
            LambdaQueryWrapper<OnlineDate> dateLambdaQueryWrapper = new LambdaQueryWrapper<>();
            dateLambdaQueryWrapper.eq(OnlineDate::getTestfileid,id);
            dateLambdaQueryWrapper.eq(OnlineDate::getResult, i);
            Long aLong = resultMapper.selectCount(dateLambdaQueryWrapper);
            integers.add(aLong);
        }

        System.out.println(integers.toString());
        return integers;
    }

    @Override
    public Long getCountByFileId(Integer id) {
        LambdaQueryWrapper<OnlineDate> dateLambdaQueryWrapper = new LambdaQueryWrapper<>();
        dateLambdaQueryWrapper.eq(OnlineDate::getTestfileid,id);
        return resultMapper.selectCount(dateLambdaQueryWrapper);
    }

    @Override
    public void downloadResultFile(String jsonUrl, HttpServletResponse response) throws IOException {
      FileUtils.downloadResultFile(jsonUrl,config.getPredictFilePath(),response);
    }
}
