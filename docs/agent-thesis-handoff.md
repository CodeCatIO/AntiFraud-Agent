# 毕设 Agent 项目交接清单

> 目标：持续完成反诈线索研判 Agent 毕设。额度或会话中断后，先看本文件，再看项目根目录 task_plan.md、findings.md、progress.md；从第一项未勾选任务接着做。勾选只表示已实现并验证，不表示“计划做”。

## 已完成

- [x] 教师确认题目、个人贡献、文本 MVP、测试评测要求和部署边界。
- [x] 自审通过详细设计，确认进入 I1；审查并修正异步回写、检测错误分数、数据迁移和实验变量四个设计缺口。
- [x] 建立 task_plan.md、findings.md、progress.md 持久计划和交接记录。

## 待办操作列表

### I1：最小纵向闭环

- [x] 复核 Java Controller、Result、TokenUtils、Mapper/Entity、异步配置，以及 Flask 文本检测接口的成功/错误响应；把字段和超时约定记入 findings.md。
- [ ] 确认新增 Agent 表的迁移脚本方案并在临时测试库验证；只新增表，不清库、不覆盖现有检测记录。
- [ ] 实现 Spring 用户侧案件/运行 API、归属检查、run_id 生成与持久化。
- [x] 完成 Agent 私有服务受控入口、一次文本工作流、检测适配与结构化结果，并通过单测。
- [x] 实现 Agent → Spring 运行事件回调；event_seq 幂等、重放不回退状态、错误可见。
- [x] 为 Flask error 响应写契约测试：即使 riskScore=0，也应转换成 failed 且 riskScore=null。
- [ ] 完成 I1 单测/接口集成测试；成功、超时、格式错误、未授权请求都覆盖后才勾阶段。

### I2：Agent 与 MCP

- [x] 为新增 Agent 服务固定 LangGraph/MCP SDK 与 Python 版本，写独立依赖锁定文件和容器配置。
- [x] 将检测适配封装为 MCP 白名单只读工具，增加 schema 校验、超时、错误归一和工具调用轨迹。
- [x] 增加知识搜索 MCP 工具的接口契约，未有知识库时明确返回 not_configured 和空结果。
- [x] 运行 MCP 契约、工作流分支、幂等回调测试并保存命令和结果。

### I3：知识库与 RAG

- [x] 建立知识卡来源/日期/定位/许可状态清单；只用合成检索查询，不收集个人线索数据。
- [ ] 对拟公开材料逐项独立核验再利用许可；未核验来源仅作内部原型，报告明确限制。
- [x] 实现知识卡导入、确定性 chunk_id、来源元数据、hash版本快照及可回查索引。
- [x] 实现 BM25、稀疏 TF-IDF 词项向量与 RRF hybrid；索引更新原子切换并可回滚。
- [x] 输出来源、段落定位和明确标记为 paraphrase 的摘要；未命中时返回空引用和无依据说明。
- [x] 建 100 条合成 retrieval 查询并分 dev/holdout，分别跑 BM25、TF-IDF、hybrid，保存 Recall@K、MRR、延迟实测。

### I4：暂停、恢复与人工复核

- [x] 固定安全版 `langgraph-checkpoint-sqlite`，用 `AsyncSqliteSaver` 和持久卷保存 LangGraph checkpoint；打开 strict msgpack 并注明单实例/轻量负载限制。
- [x] 实现规则化缺项检查、可操作追问、LangGraph `interrupt` 与补充信息恢复；事件序号跨暂停保持单调。
- [x] 实现审核通过/限定字段修改/退回、审核记录持久化及结果状态；检测和引用字段不可由审核编辑伪造。
- [ ] 验证 Agent 进程重启后从同一 SQLite 文件恢复；Spring/MySQL 对账及事件重复/乱序/延迟在 Docker Engine 可用后验收。
- [x] 验证案件跨用户读取拒绝、审核归属校验、非法决策拒绝和提示注入不能扩权；不自动报警或执行外部副作用。

### I5：测试与可复现评测

- [ ] 建立 100–200 条人工核验的合成/脱敏场景，版本化并划分开发集/留出集。
- [ ] 实现 baseline：现有检测、单轮 LLM、Agent + BM25；每个优化变量单独对照。
- [ ] 实现一键评测脚本，输出逐样例 JSONL、summary JSON、Markdown 报告和数据/模型/索引 manifest。
- [ ] 实测并报告抽取 F1、工具选择/参数有效率、Recall@K/MRR、引用可追溯/支持率、正确降级率、结构有效率、P50/P95 和成本（可获得时）。
- [ ] 加入故障注入、安全和必要性能测试；保存实测数据与失败样例，不填估计分数。

### I6：交付与毕设材料

- [x] 完成 Vue 案件提交、结果引用、审核和执行轨迹页面。
- [x] 更新 Docker Compose、健康检查、密钥配置示例、迁移/回滚/运行说明；不暴露 Agent/MCP 内部端口。（2026-10-26：Compose 挂载 V001/V002，`agent.service` 配置修复，部署文档 v2.1 补齐迁移/回滚/备份/密钥轮换/验收清单）
- [ ] 完成需求-设计-代码-测试的追踪矩阵和端到端验收。（矩阵已完成；端到端仍被 Docker Engine 阻塞）
- [x] 整理论文所需架构图、流程图、表结构、测试报告、评测结果、复用来源与个人贡献说明。（`docs/agent-thesis-paper-materials.md`）
- [ ] 复核所有阶段验收项、已知限制、文档路径和运行命令；全部通过后标记项目完成。

## 当前交接点

> 最新权威状态（2026-10-26）：Agent v4 已按 50 repeats 正式评测一次：120例、96 dev/24 holdout，整体和 holdout 的 field F1、路由准确率、schema validity 均为 1.0000；holdout P50/P95 0.0063/0.0104ms 仅含本地规则与固定草稿构造。数据集 SHA-256 `ae8a1100f4df2789aa0d23755e6859fc83bfe36055666ba82d93893886f6218f`，报告在 `agent-service/eval/agent/v4/report.md`。样例尚未独立人工核验，不代表诈骗识别准确率。v3/v4 holdout 均已查看，禁止据此继续调参。
> 最新验证（2026-10-26）：Agent 全量 pytest 27 passed；Java 回调/状态专项 12/12；本次执行 `npm run build` 通过（仅有既有大 chunk 警告）。本次修复 `agent.service` 配置层级（原先误嵌 `files` 下，生产会导致派发/事件鉴权失败）、审核参数先写检查点导致非法提交卡死 Run、重启测试断言写在 `pytest.raises` 内导致假通过；Compose 新卷自动执行 Agent 迁移，`.env.template` 移除真实密码。Docker Engine npipe 仍不存在，MySQL 迁移及端到端尚未验收。
> 下一步：核查 I3 来源许可；按可用配置尝试既有 detector baseline，缺密钥/服务时记录 not_run；Docker 恢复后仅用不带既有卷的临时 MySQL，按 `docs/部署文档.md` 11.1–11.6 完成迁移与端到端验收，再勾 I1/I4/E2E。单轮 LLM baseline 与人工核验不可伪造。
> 用户报告可用额度已降至 7%，平台额度查询工具无结果。若切换外接 DeepSeek-Flash 1070，先读本文件、task_plan.md、findings.md、progress.md；不要重跑 v3/v4，不得勾未验收项，按以上下一步继续。

- 当前阶段：I4 已实现，Python 全量回归 27/27 通过，Java 专项 12/12 通过；Vue 构建通过（有既有大 chunk 提示）。I6 部署文档与论文素材已完成，追踪矩阵已更新；I1 MySQL 迁移、Compose 启动和完整链路尚未环境验收。v3/v4 均不可再用于调参。
- 下一条具体操作：不要重跑 v3/v4，也不要再用已查看的 holdout 调参。优先核查 I3 来源许可；按可用配置尝试 detector baseline，缺服务/密钥时记录 `not_run`。Docker Engine 恢复后，按 `docs/部署文档.md` 11.1–11.6 用不带既有卷的临时 MySQL 完成迁移、Compose 健康检查和浏览器端到端，再勾 I1/I4/E2E 与 I6 最终复核。
- 后续操作顺序：更新错误表和计划日志；检查 Docker/Compose 与数据库迁移环境，Docker Engine 当前不可用，启动后仅用无既有卷的临时 MySQL 验收；补齐运行/回滚/密钥文档和论文追踪材料；保留外部检测器与单轮 LLM baseline 未运行、来源许可未独立核验等限制。
- 当前测试记录：Agent 全套 `27 passed`（2026-10-26，含修正后的重启/审核恢复用例）；Java `AgentInternalEventControllerTest,AgentRunServiceTest` 共 12/12；`docker compose config --quiet` exit 0；Vue `npm run build` 通过。Agent v4 120 条（96 dev/24 holdout）、50 repeats：overall/holdout field F1、route、schema 均 1.0000，holdout P50/P95 0.0063/0.0104 ms（仅本地规则/固定草稿，不是端到端）。报告 `agent-service/eval/agent/v4/report.md`。既有 PasswordEncoderUtilTest 基线失败仍未改动；Docker Engine 未运行，I1 迁移未做数据库级验证。
- I2 已验收：hash-pinned requirements.lock 和 requirements-dev.lock，Dockerfile按runtime lock安装；MCP 2.3.0、LangGraph 1.2.17、Python 3.12.6；MCP只读白名单/Schema/鉴权/轨迹和LangGraph分支测试通过。
- I3 实现/工程评测已验收：20张版本化知识卡、20个可回查 chunk、MCP真实检索、BM25/TF-IDF/RRF、hash索引版本及 current/previous 回滚、paraphrase 标识、100条80/20检索评测集和完整报表。数据集未人工核验，知识源许可未独立确认。
- 代码补丁记录：较大的 MCP 多文件补丁在审核阶段超时，复查确认没有落地；已改为分块操作。
- 失败处理：每次失败先记录到 task_plan.md 的错误表和 progress.md，再采取不同诊断/替代方案；同一命令不盲目重试。
- 额度/会话中断：停止新增变更前，先在本文件更新当前检查点、已验证结果和下一条具体命令；不勾选未验证项。下一位执行者从本清单首个未勾选项继续。
- 用户曾报告剩余用量约 11%，并要求额度不足时由外接 DeepSeek-Flash 1070 接续；本次用量查询工具未返回当前额度。接手前先读本文件及根目录 `task_plan.md`、`findings.md`、`progress.md`；不要重跑已完成的 v3 评测，从上方下一条具体操作或首个未勾选项继续，不得把未实测内容勾为完成。
- 设计依据：docs/agent-thesis-project-plan.md、docs/agent-thesis-requirements.md、docs/agent-thesis-technical-design.md。
