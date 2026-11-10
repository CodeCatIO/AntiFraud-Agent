package com.cucn.springboot.controller;

import cn.hutool.core.util.StrUtil;
import com.cucn.springboot.common.Result;
import com.cucn.springboot.dto.CreateAgentCaseRequest;
import com.cucn.springboot.dto.ReviewAgentRunRequest;
import com.cucn.springboot.dto.SupplementAgentRunRequest;
import com.cucn.springboot.entity.User;
import com.cucn.springboot.service.AgentRunDispatcher;
import com.cucn.springboot.service.AgentRunService;
import com.cucn.springboot.utils.TokenUtils;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import javax.annotation.Resource;
import java.util.Map;
import java.util.Collections;

@RestController
@RequestMapping("/agent")
public class AgentController {

    @Resource
    private AgentRunService agentRunService;

    @Resource
    private AgentRunDispatcher agentRunDispatcher;

    @PostMapping("/cases")
    public ResponseEntity<Result> createCase(@RequestBody CreateAgentCaseRequest request) {
        User currentUser = TokenUtils.getCurrentUser();
        if (currentUser == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(Result.error("401", "请先登录"));
        }
        if (request == null || StrUtil.isBlank(request.getContent())) {
            return ResponseEntity.badRequest().body(Result.error("400", "线索文本不能为空"));
        }
        String content = request.getContent().trim();
        if (content.length() > 10000) {
            return ResponseEntity.badRequest().body(Result.error("400", "线索文本不能超过10000个字符"));
        }
        String source = StrUtil.isBlank(request.getSource())
                ? "user_input"
                : request.getSource().trim();
        if (source.length() > 50) {
            return ResponseEntity.badRequest().body(Result.error("400", "线索来源不能超过50个字符"));
        }

        Map<String, Object> created = agentRunService.createCaseAndRun(
                currentUser.getId(),
                content,
                source
        );
        agentRunDispatcher.dispatch(
                String.valueOf(created.get("runId")),
                (Long) created.get("caseId"),
                currentUser.getId(),
                content
        );
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(Result.success(created));
    }

    @GetMapping("/runs/{runId}")
    public Result getRun(@PathVariable String runId) {
        User currentUser = TokenUtils.getCurrentUser();
        if (currentUser == null) {
            return Result.error("401", "请先登录");
        }
        Map<String, Object> result = agentRunService.getRunForUser(
                runId,
                currentUser.getId(),
                currentUser.getRole()
        );
        if (result == null) {
            return Result.error("404", "运行记录不存在");
        }
        return Result.success(result);
    }

    @PostMapping("/runs/{runId}/supplement")
    public ResponseEntity<Result> supplementRun(
            @PathVariable String runId,
            @RequestBody SupplementAgentRunRequest request) {
        User currentUser = TokenUtils.getCurrentUser();
        if (currentUser == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(Result.error("401", "请先登录"));
        }
        if (request == null) {
            return ResponseEntity.badRequest().body(Result.error("400", "补充信息不能为空"));
        }
        try {
            Map<String, Object> result = agentRunService.submitSupplement(
                    runId,
                    currentUser.getId(),
                    request.getRound(),
                    request.getAnswers()
            );
            if (!Boolean.TRUE.equals(result.get("idempotent"))) {
                agentRunDispatcher.dispatchSupplement(
                        runId,
                        request.getRound(),
                        request.getAnswers()
                );
            }
            return ResponseEntity.status(HttpStatus.ACCEPTED).body(Result.success(result));
        } catch (java.util.NoSuchElementException exception) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(Result.error("404", exception.getMessage()));
        } catch (SecurityException exception) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).body(Result.error("403", exception.getMessage()));
        } catch (IllegalArgumentException exception) {
            return ResponseEntity.badRequest().body(Result.error("400", exception.getMessage()));
        } catch (IllegalStateException exception) {
            return ResponseEntity.status(HttpStatus.CONFLICT).body(Result.error("409", exception.getMessage()));
        }
    }

    @PostMapping("/runs/{runId}/review")
    public ResponseEntity<Result> reviewRun(
            @PathVariable String runId,
            @RequestBody ReviewAgentRunRequest request) {
        User currentUser = TokenUtils.getCurrentUser();
        if (currentUser == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(Result.error("401", "请先登录"));
        }
        if (request == null) {
            return ResponseEntity.badRequest().body(Result.error("400", "审核内容不能为空"));
        }
        Map<String, Object> edits = request.getEdits() == null
                ? Collections.<String, Object>emptyMap()
                : request.getEdits();
        try {
            Map<String, Object> result = agentRunService.submitReview(
                    runId,
                    currentUser.getId(),
                    currentUser.getRole(),
                    request.getDecision(),
                    request.getComment(),
                    edits
            );
            if (!Boolean.TRUE.equals(result.get("idempotent"))) {
                agentRunDispatcher.dispatchReview(
                        runId,
                        currentUser.getId(),
                        request.getDecision(),
                        request.getComment(),
                        edits
                );
            }
            return ResponseEntity.status(HttpStatus.ACCEPTED).body(Result.success(result));
        } catch (java.util.NoSuchElementException exception) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(Result.error("404", exception.getMessage()));
        } catch (SecurityException exception) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).body(Result.error("403", exception.getMessage()));
        } catch (IllegalArgumentException exception) {
            return ResponseEntity.badRequest().body(Result.error("400", exception.getMessage()));
        } catch (IllegalStateException exception) {
            return ResponseEntity.status(HttpStatus.CONFLICT).body(Result.error("409", exception.getMessage()));
        }
    }
}
