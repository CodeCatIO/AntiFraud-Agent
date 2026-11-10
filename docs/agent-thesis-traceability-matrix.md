# 毕设需求—设计—实现—测试追踪矩阵

> 更新时间：2026-10-26。状态只依据仓库代码、当前测试和已保存评测产物；“代码/单测通过”不等于部署或端到端验收。

## 功能需求追踪

| 需求 | 设计/实现位置 | 自动化证据 | 当前结论 |
|---|---|---|---|
| FR-01 案件创建、输入校验与编号 | `AgentController`、`CreateAgentCaseRequest`、`AgentRunService.createCaseAndRun`、`V001__agent_core.sql` | `AgentRunServiceTest`；Agent API 没有真实 Spring/MySQL 集成测试 | 用户 API、文本长度/空值校验和持久化代码已实现；Controller 级测试及 DB 迁移尚未验收 |
| FR-02 缺项追问与补充续办 | `workflow.find_missing_information`、LangGraph `interrupt`、Spring supplement API | `test_missing_information_interrupts_and_resumes_with_supplement`、`test_run_waits_for_review_and_resume_finishes_with_monotonic_events`、`ownerSupplementIsStoredAndRunResumes` | 工作流/服务单测通过；端到端恢复待验 |
| FR-03 调用已有文本检测 | `agent_service/detector.py`、MCP `detect_text` | `test_detect_text_normalizes_success_response`、错误分数/缺字段/超时契约测试、只读 MCP 测试 | 合成响应与失败契约通过；真实 Flask 联调未运行 |
| FR-04 反诈知识检索与无匹配降级 | `agent-service/agent_service/retrieval.py`、`mcp_tools.py`、`agent-service/data/knowledge_sources.jsonl` | `test_versioned_index_rebuild_and_search_all_strategies`、`test_no_match_returns_empty_citations_instead_of_fabricating`、MCP 检索测试 | BM25/TF-IDF/RRF 与空引用行为通过；真实用户语义相关性未人工验证 |
| FR-05 结构化研判草稿 | `workflow.build_draft` | `test_langgraph_composes_tool_results_into_draft`、`test_failed_detection_is_reported_as_failed_run` | 固定工具 fixture 下结构与失败降级通过；不代表模型生成质量 |
| FR-06 引用来源与内容区分 | 检索结果 metadata、MCP 引用字段、Vue `AgentDraftPanel.vue` | 检索来源/定位/无命中测试；v4 schema 验证 | 来源字段、locator 和 paraphrase 标识实现；人工引用支持率未测，来源许可未核验 |
| FR-07 审核、修改、退回及审计 | `AgentReviewPanel.vue`、`AgentController`、`AgentRunService.submitReview`、`workflow.validate_review_payload`、`V002__agent_human_review.sql` | `reviewCannotEditDetectorEvidenceOrCitations`、`adminReviewIsAuditedAndMovesRunToRunning`、跨角色权限测试、非法字段在写检查点前拒绝 | API/服务与 UI 已实现并通过单测；数据库级持久化和浏览器联调待验 |
| FR-08 挂起、补充和审核恢复 | `AsyncSqliteSaver`、LangGraph `interrupt`、run/supplement/review API | `test_checkpoint_survives_saver_reopen_and_review_cannot_edit_detection`（已修正断言，真实执行非法拒绝→合法恢复）、补充恢复测试 | SQLite saver reopen 单测通过；真实进程终止/重启及 Docker 持久卷恢复未验 |
| FR-09 状态和工具运行轨迹 | Agent event callback、Spring event persistence、`AgentRunTimeline.vue` | `test_readonly_tools_use_streamable_http_and_emit_trace`、Java 幂等/乱序/重复事件测试 | 轨迹与序号逻辑有单测；完整跨服务事件链未验 |
| FR-10 工具失败可见且不伪造低风险/引用 | `detector.py`、MCP client、workflow fail-closed | `test_detect_text_treats_flask_error_score_zero_as_failure`、timeout/schema tests、`test_langgraph_fails_closed_when_detection_tool_fails` | 错误归一和本地降级契约通过；生产服务故障注入未跑 |
| FR-11 知识材料维护 | JSONL knowledge source、`build_knowledge_index.py`、hash snapshots/rollback | `test_source_import_rejects_duplicate_document_ids`、index version/rollback tests | 运维脚本导入和索引版本可用；没有带权限的前端知识维护 CRUD；P1 部分完成 |
| FR-12 固定集评测与报告 | `create_agent_eval_dataset.py`、`evaluate_agent.py` | `test_agent_dataset_has_fixed_dev_holdout_split_and_valid_gold_fields`；v4 artifacts | 自动产物存在；人工核验、真实 detector baseline 和单轮 LLM baseline 未完成 |

## 验收场景追踪

| 场景 | 证据 | 当前结论 |
|---|---|---|
| AT-01 完整线索 + 检测/检索可用 | workflow fixture test、v4 完整样例 | 本地流程测试通过；Flask/数据库/浏览器全链路未运行 |
| AT-02 缺项暂停并补充 | interrupt/resume Python tests、Spring supplement service tests | 单元/服务测试通过；跨进程/跨服务待验 |
| AT-03 检索无依据 | `test_no_match_returns_empty_citations_instead_of_fabricating` | 通过 |
| AT-04 检测超时或错误分数 | detector timeout/error-contract tests | 单测通过；真实 Flask 故障注入未跑 |
| AT-05 非法 MCP 参数/工具范围 | MCP schema rejection 与 allowlist tests | 单测通过；生产部署渗透测试未跑 |
| AT-06 审核退回与继续处理 | review controller/service code；approve/modify tests | 代码路径存在；数据库和端到端 return 流程需补验 |
| AT-07 提示注入不得扩权 | 只读 MCP allowlist、v4 注入文本样例 | 静态白名单与合成规则样例通过；完整对抗性红队评测未做 |
| AT-08 跨用户权限边界 | `reviewerCanReadAnotherOwnersRunButWorkerCannot`、worker review denial tests | Java service tests 通过；线上鉴权/审计链未验 |

## 评测与部署证据边界

- Agent v4：`agent-service/eval/agent/v4/`；120 条合成模板（96 dev/24 holdout），50 repeats；overall/holdout field F1、route accuracy、schema validity 均为 1.0000，逐例 mismatch 为 0。Dataset SHA-256 为 `ae8a1100f4df2789aa0d23755e6859fc83bfe36055666ba82d93893886f6218f`。holdout P50/P95 0.0063/0.0104 ms 只测本地规则和固定草稿构造，不是端到端。模板未人工核验，不是诈骗识别准确率。
- I3 检索报告：`agent-service/eval/results/latest/report.md`；100 条模板 query（80/20），hybrid overall Recall@1/3/5 为 0.83/0.97/1.00、MRR 0.8953；holdout Recall@1/3/5 为 0.50/0.90/1.00、MRR 0.6808。Gold 来源卡未由人工确认。
- Agent 全量 Python 测试：27 passed；Java Agent callback/service 专项：12/12；Vue `npm run build` 通过。`PasswordEncoderUtilTest.testNullAndEmpty` 是既有项目失败，不属于 Agent 改动，未修改。
- Docker Engine 当前无法通过 `npipe:////./pipe/dockerDesktopLinuxEngine` 连接；MySQL migration、Compose health readiness 和 Vue→Spring→Agent→MCP→Flask 端到端均未验收。没有清理或更改已有卷。
- 部署配置修复（2026-10-26）：`agent.service` 原误嵌在 `files` 下，`AgentServiceClient` 实际读不到配置；已移到根节点并在 `application-prod.yml` 补 `agent-service:8001` 默认值。Compose 将 V001/V002 挂到 MySQL 初始化目录，新卷自动建表；已有卷仍需手工迁移。部署文档 v2.1 已补迁移、回滚、检查点备份、密钥轮换与验收清单。
- 审核恢复缺陷（2026-10-26）：非法审核字段原先在 LangGraph 节点内才报错，此时已写入检查点，导致同一 Run 后续合法审核无法完成；现于 `resume_workflow` 调用 `ainvoke` 前校验，测试已能真实覆盖“非法拒绝后合法恢复”。
- 外部检测器、单轮 LLM baseline、人工引用支持率和模型调用成本均未实测；不得填写估计值。知识材料的再利用许可尚未独立核实。

## 完成此矩阵后的剩余门禁

1. 人工复核合成集标签/模板；取得可审计的来源授权或进一步限定为内部原型。
2. 运行或明确记录真实 Flask detector baseline；配置可用模型后再做单轮 LLM 对照，记录模型/提示/成本/日期。
3. Docker Engine 可用后，在不连接既有卷的隔离数据库上执行迁移、回滚和完整链路验收。
4. 补齐部署运行、健康检查和安全密钥文档；完成浏览器端到端检查与所有未验收标记复核。（文档已于 2026-10-26 补齐，见 `docs/部署文档.md` 第十一节；浏览器端到端仍待 Docker）
