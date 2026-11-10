# 项目发现与设计决策

## 已确认的用户/老师要求

- 题目无需改动：面向电信诈骗线索研判的可控智能体工作流系统设计与实现。
- 可复用宿舍比赛项目代码和数据，但要说明个人贡献、来源及团队授权/脱敏边界。
- 本人负责 Agent 工作流、MCP 工具接入、RAG 引用、人工复核与评测；不冒领室友的检测模型、证据存证和可视化成果。
- MVP 以文本线索为主；语音/图像非本期必做。
- 学院未指定评测指标阈值；要有测试和可运行评分脚本，优化前后报告真实数据。
- 未要求具体部署、数据库或模型平台。

## 仓库现状（2026-10-26 复核）

- 项目目录：ai_-anti_fraud_-software-master；该目录不是 Git 仓库，git diff --stat 报 not a git repository。
- 前端 Vue；后端 Spring Boot 2.5.9、Java 8、MyBatis-Plus；Python Flask AI 服务；Docker Compose 已配置 MySQL 8 与 Redis 7。
- Spring Result 是 code/msg/data 三字段；文本入口为 DetectController 的 POST /detect/text，需当前用户并写 detection_record。
- AiServiceClient 调 Flask POST /api/detect/text。Flask 成功响应含 riskScore、riskLevel、model、detail 等字段；错误响应由 _make_error 返回 error，同时也带 riskScore=0、riskLevel=检测失败。Agent adapter 必须优先检查 error，不能把 0 解释为正常低风险。
- RestTemplateConfig 为现有 AI 客户端配置 connect timeout 默认 5000ms、read timeout 默认 30000ms。Agent 新服务应使用独立可配置超时，并让上游运行总超时大于单次工具 read timeout。
- DetectionRecord 使用 MyBatis-Plus @TableName/@TableId(AUTO)，对应 Mapper 继承 BaseMapper；Spring Controller 返回 Result(code,msg,data)，当前用户由 TokenUtils.getCurrentUser() 获取。
- Redis 配置已在 Compose 中启用 AOF，但 Agent checkpoint 适配器、连接密码和恢复语义尚未实现验证。
- sql/anti_fraud.sql 是 Docker MySQL 空数据目录的初始化脚本；不能依赖它升级已有 volume。新表需单独版本化、非破坏性迁移。
- 仓库没有检出 Flyway/Liquibase。Maven 已含 spring-boot-starter-test。
- 新 Agent/MCP Python 运行时独立于现有检测服务的 Python 3.10 镜像；具体依赖要锁版本并通过容器构建验证。

## I1 接口复核（已完成）

- Flask POST /api/detect/text 接受 JSON content 和可选 model；默认模型为 ensemble。成功响应包含 riskScore、riskLevel、model、modelLabel、detail、keywords、patterns。
- Flask 错误响应包含 error、riskScore=0、riskLevel=检测失败、detail；HTTP 4xx/5xx 时同样必须当作失败，禁止把风险分解释为 0。
- 现有 Java 文本入口需用户登录且写检测记录；Agent 工具直连 Flask 内网接口，不使用浏览器 JWT，Agent 的关联记录单独入库。
- 现有 Java AI RestTemplate 默认连接超时 5 秒、读取超时 30 秒；Agent 工具适配器要自行配置并记录各次调用耗时。
- backend/src/test/java 已有 Spring Boot、HealthController、密码和 TokenUtils 测试；Maven 含 spring-boot-starter-test。
- 本机 Python 3.12.6 可用，pytest、Flask、FastAPI、httpx、LangGraph 和 MCP 包当前均可导入。python3 Windows Store alias 不可启动，后续明确使用 python.exe。
- Java 当前命令 shim 访问被拒绝，但机器上可见 JDK 17 安装路径 D:/Path_Or_Misc/JDK17；运行 Maven 时应临时把 JAVA_HOME/PATH 指向该 JDK，避免 Java 8 shim。
- 在 Windows 受限沙箱执行 pytest 时，第一项通过后卡在第二项；独立 asyncio.run(health()) 也卡在 Python 3.12 Proactor _fallback_socketpair 的 socket.accept。faulthandler 指向本地 socket 初始化而非应用函数。当前未得到 Python 测试退出码，不能宣称测试失败或通过；需在批准的沙箱外或 Linux 容器重试。

## 设计决定

- Spring Boot 为用户鉴权与业务记录入口；Agent、MCP 服务部署于内网。
- Agent 异步受理；Agent 通过带 run_id/event_seq 的内部事件回调更新 Spring/MySQL。回调至少一次、按 run_id + event_seq 幂等；MySQL 状态供前端查询，SQLite checkpoint 用于 Agent 流程恢复。
- 检测和知识检索为只读白名单工具；用户线索和文档视为不可信输入。
- 先用最小端到端闭环验证接口，后逐步叠加 MCP、RAG、HITL 和评测，不把全部设计一次性塞入 I1。
- 检索优化对比一次只改一个变量：BM25、dense、hybrid 分别测；reranker 如加入则单独实验。
- 官方 MCP Python SDK 文档当前将 v2 标为 stable；新项目使用 MCPServer 与 Streamable HTTP，旧 v1 的 FastMCP 导入/API 不可照搬。I2 编码前必须按锁定版本核对 API，并保留 SDK 契约测试。
- I1 代码现状：Spring 侧已新增案件/运行/事件实体与 Mapper、用户侧提交和归属查询、Agent 私有调用以及共享密钥保护的事件回调；Python Agent 端目前依赖 FastAPI BackgroundTasks 和进程内 run_states，尚不具备重启恢复能力，不能当作最终可靠执行器。I4 需切到持久化 checkpoint/恢复并用真实重启测试验收。
- 部署现状：Compose 中 Agent 服务只在默认容器网络暴露 8001，不发布宿主机端口；backend/agent 共用必填 AGENT_SERVICE_TOKEN，经 .env 配置。现有 .env 与数据库卷未读取或更改；docker compose config --quiet 已通过。
- 更新验证记录：沙箱外 Python pytest 当前 10 passed。Maven 编译生产源码 92 个文件及测试源码 5 个文件通过，但 surefire 未启动测试，缺 junit-platform-launcher:1.7.2；不能把 Java 编译通过描述成测试通过。
- 本机 Docker Desktop CLI 存在但 Linux Engine 未运行（npipe 管道缺失）；未运行临时数据库，也未碰现有 MySQL/Redis 容器和数据卷。迁移尚未获得数据库级验证。
- Maven 在线下载 junit-platform-launcher 时可访问配置的 Aliyun URL，但本地沙箱拒绝写入 C:/Users/BQY/.m2/repository；当前仍无 Java 测试退出码。申请受控沙箱外运行以写入常规 Maven 缓存并执行目标单测。
- Java 测试实际结果：AgentInternalEventControllerTest 2/2 passed；TokenUtilsTest 5/5 passed；PasswordEncoderUtilTest 5/6，既有 testNullAndEmpty 失败（预期 false、实际 true）。这项与 Agent 范围无关，暂时不修改。独立 Agent 单测通过，不等于数据库端到端集成已通过。
- I2 官方 API 决策：MCP Python SDK 官方发行记录显示 2.3.0 为当前稳定 v2 release；Python 要求 3.11+。新 MCP server 用 MCPServer + Streamable HTTP，测试使用官方 in-process Client(mcp) 模式；tool call 应检查 is_error 并读取 structured_content。LangGraph 官方文档将 checkpointer 定义为 thread 级短期状态，SQLiteSaver 为本地持久方案；interrupt 需要 checkpoint 与 thread_id，并以 Command(resume=...)恢复。
- Agent 依赖本地版本基线：Python 3.12.6、FastAPI 0.136.3、httpx 0.28.1、uvicorn 0.51.0、Pydantic 2.12.5、LangGraph 1.2.17；MCP 本机为 1.28.1，需要在 Agent 私有运行环境升级到精确锁定的 2.3.0 后测试，不能混用 v1/v2 API。
- 已生成带 hash 的 requirements.lock / requirements-dev.lock；运行时 58 个解析包，测试锁追加 pytest 9.1.1；Dockerfile 仅按运行时 lock 安装。项目 .venv 已按 dev lock 安装63个包，MCP 2.3.0/LangGraph 1.2.17验证通过。
- I2验收：精确 .venv 下16 pytest passed；MCP HTTP接口由middleware共享token保护，Agent调用只读白名单tools/list与tools/call；Java AgentInternalEventControllerTest + AgentRunServiceTest 6 tests passed，覆盖event_seq幂等及终态不回退。
- I3来源限制：已核对工信部反诈法页面、司法部普法平台转载的公安部刑侦局/国家反诈中心2025版手册发布摘要、2026版手册发布摘要以及国家应急广播转载的公安部2021防范指南。2025/2026发布页不是手册全文；索引不能把类别名扩写成未被来源支持的行为事实。记录source_url、title、date、article locator、index/source version及未独立核验的许可状态。
- I3 retrieval implementation: cards are parsed as JSONL and validated before indexing; each card maps to a deterministic content-hash chunk, with immutable SHA-256-derived index snapshots and atomic current/previous pointers. Runtime supports BM25, sparse TF-IDF lexical vectors, and RRF; snapshots/tokenization are process-cached. Citations contain source URL/publisher/date/locator/version/chunk id and mark the snippet as a paraphrase.
- I3 benchmark snapshot: dataset SHA-256 is stored in `agent-service/eval/results/latest/manifest.json`; 100 generated template queries (80 dev/20 holdout), labels point to source-card IDs and are not manually reviewed. Overall hybrid Recall@1/3/5=0.83/0.97/1.00, MRR=0.8953; holdout MRR=0.6808. Do not cite as human relevance or fraud-classification accuracy.
- I3 legal/reuse limitation: source card `license_status` is `not_independently_verified`. This is a transparent provenance status, not a reuse grant; verify the rights before thesis/public distribution.
- I4 checkpoint decision: use `langgraph-checkpoint-sqlite==3.1.2` with `AsyncSqliteSaver` on a Docker named volume for this single-instance/light-load thesis MVP, not the existing plain Redis 7 image (Redis checkpointer requires JSON/Search modules). Set strict msgpack, keep `thread_id` to server-generated UUIDs, expose no user-controlled checkpoint filters, and document SQLite throughput/single-instance limits. Official repo release/advisory verify 3.1.2 is the namespace-isolation fix; SQLite saver itself warns that it is not intended for production-scale write throughput.
- 部署配置发现（2026-10-26）：`AgentServiceClient` 与内部事件控制器读取 `agent.service.base-url` / `agent.service.shared-secret`，但这两个键此前被误写在 `files` 下，实际只回落到默认 `http://localhost:8001` 和空密钥。dev 直连可能“碰巧能用”，生产容器里后端拿不到 `AGENT_SERVICE_TOKEN`，派发与事件回写会 401。现已移到 `application.yml` 根节点，并在 `application-prod.yml` 增加 `http://agent-service:8001` 默认值。
- 审核恢复缺陷（2026-10-26）：非法审核字段原先在 `finalize_review` 节点内才校验，LangGraph 已把 resume 值写入 checkpoint，导致该 Run 后续合法审核一直重放非法值。`resume_workflow` 现在在 `ainvoke` 前调用 `validate_review_payload`；测试修正后真实覆盖“非法被拒 → 合法恢复完成”。
- 迁移部署边界：Compose 把 V001/V002 挂到 MySQL `/docker-entrypoint-initdb.d`，只对全新数据卷生效；已有卷必须手工执行 `CREATE TABLE IF NOT EXISTS` 迁移，不能依赖重启容器。
- I4 retention: keep raw text in checkpoints only while a run is paused/running; delete the graph thread only after the final Spring event callback is acknowledged. If callback delivery fails, retain the checkpoint for recovery. Paused checkpoints currently have no automatic expiry and must be managed as sensitive data.
- I4 authorization review found that the service's previous run-read query constrained `user_id` before checking reviewer role, preventing authorized reviewers from opening another owner's run. The query now loads the case by ID and applies owner-or-reviewer authorization; raw case content is returned only through that protected endpoint for human review.
- I5 benchmark iteration 1: the 120-case synthetic rules benchmark initially scored field F1 0.9739 and route accuracy 0.9083; all route errors were negated claims or channel false positives. We inspected errors in both dev and holdout, so that holdout is contaminated and cannot be reported as independent evaluation. Rule fixes address negation and remove broad `APP`/`平台` channel matches; regenerate a fresh held-out set and keep it untouched. The synthetic templates and gold labels still need independent student/advisor review.
- The Flask text detector already includes an optional DeepSeek LLM semantic layer. No external model call was made during this work; local tests/benchmarks use fixed outputs. Distinguish Agent's deterministic draft and workflow from the existing detector's optional LLM layer in thesis claims.
- Agent benchmark v3: 120 generated templates (96 dev/24 holdout), 50 repeats, dataset SHA-256 `ce92b8174f806c9fd824ce71f6c920712c0bb2ff6405958a5fe014f771891d30`; artifacts in `agent-service/eval/agent/v3/`. Overall field F1 .9963, route .9917, schema 1.0; holdout F1 .9801, route .9583, schema 1.0. Latency only measures local rules and fixed draft construction. Inspection found two gold time-vocabulary mismatches (`heldout-001`, `heldout-018`) and one identity-negation miss (`heldout-019`: “没有人自称银行职员”). This holdout has now been inspected; do not use it for further tuning. Add observed patterns to dev, correct labels, then create a fresh v4 holdout before another independent measurement. These synthetic checks are not fraud-detection accuracy.
- Docker availability rechecked 2026-10-26: `docker info` cannot connect to `npipe:////./pipe/dockerDesktopLinuxEngine`; no containers or volumes were touched, migration remains unverified.
- Agent benchmark v4 supersedes the inspected v3 dataset for current regression measurement. v4 SHA-256 `ae8a1100f4df2789aa0d23755e6859fc83bfe36055666ba82d93893886f6218f`; 120 synthetic cases, 96 dev/24 holdout, 50 repeats; all field/route/schema metrics are 1.0000 and per-case mismatch count is zero. P50/P95 on holdout .0063/.0104ms only cover local rules/fixed draft fixture. Artifacts are under `agent-service/eval/agent/v4/`; human review is still pending and holdout must not be used for further tuning.

## 交接规则

- 先读 docs/agent-thesis-handoff.md，继续第一项未完成工作。
- 失败必须记入 task_plan.md 和 progress.md：保留错误、尝试次数、诊断和替代方案；不勾选未通过阶段。
- 修改文件后跑与改动相关的最小测试，再决定是否扩大验证。
