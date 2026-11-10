package com.cucn.springboot.controller;

import com.cucn.springboot.common.Constants;
import com.cucn.springboot.common.Result;
import com.cucn.springboot.service.IPredictService;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import javax.annotation.Resource;
import javax.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.List;

/**
 * 文件上传相关接口
 */
@RestController
@RequestMapping("/DataTest")
//@Transactional
public class PredictController {

    @Resource
    private IPredictService predictService;


    @PostMapping("/upload")
    public Result upload(@RequestParam MultipartFile file) throws Exception {

        if(null == file)
        {
            return Result.error(Constants.CODE_400,"上传的文件为空,请上传文件！");
        }

        predictService.uploadPredictFile(file);

        return Result.success();
    }

   // @Async
    @GetMapping("/getUrl/{url}")
    public Result beginPredict(@PathVariable String url) throws IOException {
        System.out.println("开始多线程,在线预测 + url");
        // 根据文件的唯一标识码获取文件
        long stime = System.currentTimeMillis();

        Result response = predictService.beginPredict(url);

        // 结束时间
        long etime = System.currentTimeMillis();
        // 计算执行时间
        System.out.printf("执行时长：%d 毫秒.", (etime - stime));
        System.out.println("结束多线程,在线预测结束");
        return response;
    }

    /**
     * 分页查询预测列表
     * @param pageNum
     * @param pageSize
     * @param name
     * @return
     */
    @GetMapping("/page")
    public Result findPage(@RequestParam Integer pageNum,
                           @RequestParam Integer pageSize,
                           @RequestParam(defaultValue = "") String name) {

        return Result.success(predictService.findPage(pageNum,pageSize,name));
    }

    @Transactional
    @DeleteMapping("/{id}")
    public Result delete(@PathVariable Integer id) {
        predictService.deletePredictData(id);
        return Result.success();
    }


    @PostMapping("/del/batch")
    public Result deleteBatch(@RequestBody List<Integer> ids) {
        predictService.deleteBatch(ids);
        return Result.success();
    }

    @GetMapping("/detail/{id}")
    public Result getById(@PathVariable Integer id) {

        return Result.success(predictService.getById(id));
    }

    @GetMapping("/totle")
    public Result totle() {

        return Result.success(predictService.predictTotle());
    }

    @GetMapping("/members/{id}")
    public Result members(@PathVariable Integer id) throws IOException {

        return Result.success(predictService.getMalfunctionCount(id));
    }




    @GetMapping("/totle/{id}")
    public Result totle(@PathVariable Integer id) {
        return Result.success(predictService.getCountByFileId(id));
    }

    @GetMapping("/{jsonUrl}")
    public void download(@PathVariable String jsonUrl, HttpServletResponse response) throws IOException {
        predictService.downloadResultFile(jsonUrl, response);
    }
}
