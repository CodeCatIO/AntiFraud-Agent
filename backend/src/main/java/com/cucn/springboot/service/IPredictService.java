package com.cucn.springboot.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.cucn.springboot.common.Result;
import com.cucn.springboot.entity.TestFiles;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.multipart.MultipartFile;

import javax.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

/**
 * @BelongsProject: Software-Cup
 * @BelongsPackage: com.cucn.springboot.service
 * @Author: liumei
 * @CreateTime: 2023-10-18  16:05
 * @Description: TODO
 * @Version: 1.0
 */
public interface IPredictService {

    boolean uploadPredictFile(MultipartFile file) throws Exception;


    Result beginPredict(String url) throws IOException;

    IPage<TestFiles> findPage(Integer pageNum,
                             Integer pageSize,
                             String name);

    boolean deletePredictData(Integer id);

    boolean deleteBatch( List<Integer> ids);

    TestFiles getById( Integer id);

    /**
     * 当年预测的次数
     * @return
     */
    Integer predictTotle();

    /**
     * 获取六个种类故障的个数
     * @param id
     * @return
     */
    ArrayList<Long> getMalfunctionCount(Integer id);

    /**
     * 按照单个预测文件的计算故障的个数
     * @param id
     * @return
     */
    Long getCountByFileId(Integer id);

    void downloadResultFile( String jsonUrl, HttpServletResponse response) throws IOException;
}
