# 进度日志

## 2026-11-10
- A（完成）：Docker Engine 可用后已 `docker compose build` + `up -d`，6 个容器全部 healthy：mysql(3307)、redis(6380)、ai(5000)、agent(内部 8001)、backend(9090)、nginx(80)。修复的真实阻断：Redis 空密码时 `--requirepass` 无参数导致容器崩溃；后端运行镜像 `openjdk:17-slim` 换为 `eclipse-temurin:17-jre-jammy`；agent-service 误带 Windows 专属 `pywin32` 与超时拉包（改清华源 + requirements.txt）；AI 容器缺 `pandas`/`scikit-learn`；Docker Hub 镜像源 `hub-mirror.c.163.com` 失效。本机 3306/6379/9090 被原生进程占用，改用 `.env` 端口变量 3307/6380。前端改为多阶段构建进 Nginx，同源 `/api` 反代，成为可上线的单一入口。
- B（完成）：注册 500 根因是 `sys_role` 缺少 `RoleEnum` 使用的 `ROLE_WORKER`/`ROLE_MAINTENANCE`；新增幂等迁移 `sql/migrations/V003__seed_roles.sql` 并挂载 Compose。实测注册/登录正常；非本人补充信息返回 403；5 张 agent 表、事件幂等、审核权限均通过单测与实测。
- C（完成）：实测双暂停点（信息补充、人工审核）可恢复；引用含 `locator`/`chunkId`/来源链接；检测失败不降级为低风险；工具白名单为只读三项。
- D（完成）：Agent pytest 27 passed；Java 定向测试 17 passed；120 案例 50 repeats：overall/holdout field F1、路由、schema 均 1.0；检索 100 queries：overall R@1=.83、R@3=.97、R@5=1.0、MRR=.8953；holdout R@1=.50、R@3=.90、R@5=1.0、MRR=.6808。证据目录 `agent-service/eval/agent/run-20261110`、`agent-service/eval/results/run-20261110`。
- E（完成）：线索详情工作台新增 `AgentRunProgress` 进度条、草稿引用编号与出处编号、右上角“去提审”按钮；已有任务时隐藏新建表单，移动端单列布局。`npm run build` 通过，1440px/390px 截图验收无溢出。
- A/E 容器验收：经 `http://127.0.0.1/api`（Nginx 同源）完成注册、登录、建案、`WAITING_FOR_REVIEW`（5 条引用）、审核、`COMPLETED`；Playwright 无头浏览器验收进度条 1、待审核 2、去提审 1、出处编号 5，console error 0。
- 安全收尾：默认管理员口令由 `123456` 改为 `AntiFraud@2026`（旧口令返回业务码 600）。修复所有用户接口把 BCrypt 哈希回传前端的问题——`User`/`UserDTO` 的 `password` 改为 Jackson `WRITE_ONLY`，登录、注册、`/user`、`/user/{id}`、`/user/getUserName`、`/user/page` 响应均不再含 `password`；用户 Excel 导出前清空密码哈希。`.env` 首行 `DEEPSEEK_API_KEY` 与 `AGENT_SERVICE_TOKEN` 粘连、重复定义已拆开。
- 编码修复：容器内 mysql 客户端初始化时按 latin1 解析脚本，导致种子中文双重编码（`管理员` 存成 `C3A7C2AE...`，页面右上角显示乱码）。四个初始化脚本（`anti_fraud.sql`、`V001`、`V002`、`V003`）开头补 `SET NAMES utf8mb4;`，删除旧数据卷重建后 HEX 校验为 `E7AEA1E79086E59198`（=管理员），浏览器实测右上角显示“管理员”。重建前已用 mysqldump 备份到 `%TEMP%\anti_fraud_backup.sql`；重建后重跑双用户 E2E：建案 → `WAITING_FOR_INFO` → 补充 → `WAITING_FOR_REVIEW`（5 条引用）→ 管理员 `approve` → `COMPLETED`；创建人自审返回 403（职责分离生效）。
- F（部分完成）：
  - 演示录屏 `docs/assets/demo.mp4`（46 秒，1920×1080，含音轨，15 MB）：Playwright 原始录制 2 分 40 秒，经人工剪辑为 46 秒成片；内容是研判员建案 → 信息补充 → 带 5 条出处草稿 → 切换管理员复核 → 已完成（100%、5 条轨迹）；录制时 console error 0。
  - 可用性测试方案与报告 `docs/可用性测试报告.md`：任务卡 T1–T5、SUS 量表、记录表、指标定义、预演时间线与 5 条问题清单（P1 补充问题格式提示不足等）。**3 名真人测试尚未执行，报告内记录表保持空白，未编造真人数据。**
  - README 增补“交付物与验收材料”表与录屏时间点；修正登录示例口令为 `AntiFraud@2026`；Docker 段补 Nginx 入口、默认账号与端口变量说明。
  - 论文初稿 `docs/论文初稿.md`（约 9000 字，8 章 + 15 条参考文献）已完稿；第 6 章数字已回查 `agent-service/eval/results/run-20261110/` 一致，第 7 章如实标注 3 人测试未执行。

## 2026-10-26
- I6 收尾（18:20）：修复 Spring `agent.service` 配置误嵌 `files` 导致的生产派发/鉴权失效；`application-prod.yml` 补内网默认值；Compose 为新 MySQL 卷挂载 V001/V002；`.env.template` 移除真实密码；部署文档升级 v2.1（迁移/回滚/检查点备份/密钥轮换/验收清单/验证边界）；新增 `docs/agent-thesis-paper-materials.md`。发现并修复审核恢复缺陷：非法审核字段原先先写入 LangGraph checkpoint 才报错，导致同一 Run 后续合法审核永远失败；现在 `resume_workflow` 在 `ainvoke` 前校验。修正重启恢复测试把合法恢复写在 `pytest.raises` 内的假通过问题。复测 Agent 27 passed、Java 12/12、`docker compose config --quiet` exit 0；Docker Engine 仍不可用，迁移/E2E 未验收。
- 最新更新（覆盖下方早先“v3 尚未评测”记录）：v4 合成数据集生成并进行一次 50-repeat 正式评测；overall/holdout field F1、路由、schema 均 1.0，holdout mismatch 0。SHA-256 `ae8a1100f4df2789aa0d23755e6859fc83bfe36055666ba82d93893886f6218f`，report `agent-service/eval/agent/v4/report.md`。v3/v4 holdout 均已查看，不得再据此调参。v4 专项 11 passed，全量 Agent pytest 27 passed。Docker Engine 仍不可用；I1 MySQL 迁移/端到端未验收。用户报告剩余用量 7%，额度查询工具无结果；handoff 已记录 DeepSeek 接手指引。

- I5 用例补丁首次因测试函数预期结束行不匹配而失败；未写入文件。随后读取准确函数内容，按实际位置重试。
- I5 README 评测说明补丁因上下文位置不准确失败，未修改文件；下一步检查实际段落并追加。
- I5 v3 数据集一次性大补丁审批超时但实际部分落地（开发循环数改为64/16/8/8）；补丁重试因已变更上下文失败。计划记录修订的多文件路径也被拒绝；已复核文件并改为单文件更新，后续保留旧v2输出。
- 2026-10-26：v3 已生成并只跑一次（50 repeats），Agent pytest 27 passed。整体 field F1=.9963、route=.9917、schema=1.0；holdout F1=.9801、route=.9583、schema=1.0；holdout P50/P95=.0068/.0101ms（本地规则/固定 fixture，不是端到端）。SHA-256 `ce92b8174f806c9fd824ce71f6c920712c0bb2ff6405958a5fe014f771891d30`。检查样例后发现 heldout-001/018 的时间标签超出规则词表、heldout-019“没有人自称”漏判；holdout 已查看，禁止在 v3 上调参，后续需新 v4 holdout。Docker Engine npipe 仍不存在，DB 迁移未验收。额度查询工具不可用，已按用户要求更新 DeepSeek 接手记录。

- D0 需求确认：complete。用户转述教师确认题目、边界、文本 MVP、评测偏好和部署自由度。
- D1 详细设计：complete。形成 docs/agent-thesis-technical-design.md，并按自审修正异步状态回写、检测失败分数、数据库迁移和实验控制变量问题。
- 计划恢复检查：项目没有 .planning 目录、PLAN_ID 或 PWF_PLAN_ROOT；采用项目根目录 legacy 计划文件。
- Git 状态检查：git diff --stat 失败，因为项目不是 Git 仓库；已记录，不再重复。
- 尚未开始 I1 源代码实现；没有 Agent 测试或实测跑分。
- I1 接口复核完成：Flask 文本 API 输入、成功/错误字段，Java 当前用户鉴权、MyBatis-Plus 约定和现有 5s/30s 超时默认值已记录进 findings.md。
- Python 3.12.6 及 pytest、Flask、FastAPI、httpx、LangGraph、MCP 可导入；Java 测试位于 backend/src/test/java；Maven 测试依赖存在。Java 命令 shim 受拒绝，执行 Maven 时使用已安装 JDK 17 的显式 JAVA_HOME/PATH。
- 当前下一步：新增非破坏性迁移和 Agent 服务调用契约，再实现 I1。
- 官方 MCP SDK 文档复核：当前 v2 使用 MCPServer/Streamable HTTP；记录为 I2 实施约束，尚未开始安装/改动项目依赖。
- I1 初始增量已创建：独立 SQL 迁移、Python 3.12 Agent API/Dockerfile、Flask 检测错误归一、异步回调机制和 6 个 Python 单测。
- Python 测试阻塞：pytest 第一项通过后卡住；独立 asyncio 诊断的 faulthandler 定位到 Windows Proactor 创建本地 socketpair 时在 socket.accept 等待。进程已中断，没有通过/失败退出码。下一步先寻求沙箱外或容器内运行方式，并继续 Java 后端闭环。
- 继续 I1：新增 Spring 案件/运行接口、MySQL 事件回调、event_seq 幂等、归属校验和异步派发；仅代码存在，构建和测试仍未验证。
- 继续 I1：docker-compose 增加无宿主机端口的 agent-service、内网依赖/健康检查，Spring 和 Agent 使用同一必填 AGENT_SERVICE_TOKEN；.env.template 增加占位说明；未修改现有 .env 或 MySQL volume。
- 补丁失败记录：第一次配置补丁使用了不匹配的 JWT 模板行，校验失败且未写入；重新按真实上下文更新成功。绝对路径 apply_patch 审核超时后改相对路径重试成功。
- I1 Python 验证：沙箱外执行 pytest，10 passed（含上游超时归一、Flask error 零分不得作为低风险、事件回调重试、run_id 冲突、失败检测状态）。
- I1 Maven：首次运行 BUILD SUCCESS 但 pom.xml 硬编码 skipTests=true，未运行测试；现已移除禁用并升级到缓存的 Surefire 3.5.4，新增 Spring 内部事件回调鉴权单测。mvn -o -Dtest=AgentInternalEventControllerTest test 的生产和测试源码编译通过，但 surefire 因本机缓存缺 org.junit.platform:junit-platform-launcher:1.7.2 而失败，尚无 Java 测试结果；下一步尝试在线依赖解析。
- Compose：临时注入非真实校验 token 后 docker compose config --quiet 退出码 0，无配置语法错误；不会打印/读取当前 .env 密钥。
- 迁移验证受阻：Docker CLI 可用，但 Linux Engine 管道不存在，docker image inspect/ps 均无法连 daemon；没有创建或修改容器/volume。下一步等待 Docker Engine 可用后使用无 volume 的临时 MySQL 验证迁移。
- 当前下一步：在线重试 Maven 目标单测；继续实现/验证剩余 Agent 与流程功能，Docker 数据库级迁移验证保留为未完成。
- Maven 在线重试：目标代码仍编译通过，但下载 junit-platform-launcher 时 AccessDeniedException 写入 C:\Users\BQY\.m2\repository；在沙箱限制下没有 Java 测试结果。下一步对该只读依赖缓存目录使用受控沙箱外 Maven 执行。
- 交接文档更新补丁因旧 Next Step 文案不一致失败一次，未写入；重新核对当前文字后追加记录。
- 一次多类 Maven 测试命令未启动：PowerShell 将逗号分隔的 -Dtest 选择器当作表达式报 ParserError。下一次把完整参数引号包裹后运行。
- MCP v2/LangGraph 测试最终结果：精确锁定 .venv 下 pytest 16 passed，覆盖白名单与schema、内部Streamable HTTP共享token、结构化检索空结果、LangGraph成功/失败状态。命令：agent-service/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider。
- I1 Java 状态/幂等专项：6 passed，覆盖终态事件重复不回退、终态不接受后续 RUNNING、序号缺口拒绝、合法下一个序号保存draft、回调token。
- I2 验收：依赖/容器锁、MCP白名单检测和知识搜索契约、LangGraph工作流、工具轨迹、MCP/分支/回调单测均完成，I2 在交接清单勾选完成。I1数据库迁移和完整 Spring→Agent→Flask 端到端仍因 Docker Engine 未启动而未验收。
- I3 来源核验：工信部反诈法页面、司法部普法平台转载的公安部刑侦局/国家反诈中心2025版手册发布页、2026版手册发布摘要及国家应急广播转载的公安部2021防范指南。知识卡只做有来源标注的简要转述，不从摘要臆造具体案情。
- 阶段总结补丁曾因旧 Next Step 上下文失败两次、均未写入；现分文件按当前内容更新。
- I2 依赖已固定：FastAPI 0.136.3、httpx 0.28.1、uvicorn 0.51.0、LangGraph 1.2.17、MCP SDK 2.3.0、pytest 9.1.1；uv pip compile 在受控联网下生成 requirements.lock 与 requirements-dev.lock，含 58 个运行时/传递包并带 SHA-256 hashes（dev 锁另含 pytest）。Dockerfile 改为按锁安装，.uv-cache 加入忽略规则。
- Dockerfile 补丁审批超时一次，绝对不假定写入；改用相对路径再试后已成功。下一步隔离 venv 同步 dev lock 并跑 SDK v2 兼容测试。
- MCP 多文件补丁审核超时；复查确认没有部分改动。下一步拆分为 mcp client 注入、API 测试适配、独立 MCP 测试文件，逐块应用。
- I1 Java 回调专项：mvn -o -Dtest=AgentInternalEventControllerTest,AgentRunServiceTest test，6 tests run、0 failures/errors；覆盖共享密钥、事件重复、终态不回退、序号缺口和顺序持久化。
- 当前完整 Agent pytest 沙箱外执行申请在启动前被审批超时拒绝，没有测试进程/退出码；记录后重试一次。
- Maven 受控沙箱外目标测试已执行：AgentInternalEventControllerTest 2/2 通过，TokenUtilsTest 5/5 通过；PasswordEncoderUtilTest 5/6，其中既有 testNullAndEmpty 断言失败（期望 false 实际 true），属于不相关的原有行为，未按“不要修复无关问题”原则改动。
- I2 锁文件首次生成未开始解析：uv 默认试图写入受限 AppData sandbox cache，权限拒绝；requirements.lock 尚不存在。下一步把 UV_CACHE_DIR 改到 agent-service 目录内重试。
- I2 锁文件第二次尝试已把 UV_CACHE_DIR 放在工作区，但访问 pypi.org 因套接字策略被拒绝，未生成 requirements.lock。下一步为 uv lock generation 请求受控沙箱外执行；若审批不通过则使用本地运行时装包信息生成无 hash pin 锁并明确校验限制。
- Agent + Token 两组单测可作为专项通过结果；包含既有 PasswordEncoderUtilTest 的组合命令总计 13 项、1 失败，不能报告整组 BUILD SUCCESS。
- I3实现中：已增加来源元数据校验、稳定 chunk_id、hash版本快照、current/previous 指针和BM25/TF-IDF/RRF检索，MCP search_knowledge已调用本地索引；补充精确策略测试。首次用 `python scripts/build_knowledge_index.py` 启动失败，因为脚本目录而非项目根被加入sys.path，未生成产物。标准运行方式改为从agent-service目录执行 `python -m scripts.build_knowledge_index`，随后重跑生成/评测。
- I3 评测脚本现支持按 dev/holdout 分项统计；追加对应单测时一次 apply_patch 审批超时，检查确认测试文件未落盘。已记错误，下一步以更小补丁重试一次。

## 错误

- JS 模板字符串传递 Markdown code fence 导致一次 SyntaxError；重试时移除代码围栏，设计文档补丁成功。
- 创建计划文件时行内反引号未转义导致一次 ReferenceError；尚未写入文件，已改成纯文本后重试。
- git diff --stat 不可用，因为项目目录没有 Git 元数据。替代为规划文件记录、测试产物和变更文件清单。
- Python Store 的 python3.exe alias 无法启动；已改用明确的 D:/Program File/Python3.12/python.exe。
- 默认 java.exe shim 访问被拒绝；已找到 JDK17 安装路径，后续显式设置 JAVA_HOME，不重复调用被拒绝路径。
- 计划更新补丁因上下文过期失败一次；重新核对当前文件内容后按实际文案更新。
- 首次 Agent 源码补丁被 SQL 反引号打断，未修改文件；移除标识符引号后创建成功。
- pytest 与直接 asyncio.run 在受限沙箱内均卡在事件循环 socketpair 初始化；堆栈已记录，需改用不同执行环境验证。
- rg 对 PowerShell 风格 -ErrorAction 参数报 unknown encoding；未影响数据，改用 PowerShell 原生命令枚举测试目录。
- I3 检索实现：新增 `retrieval.py`（JSONL元数据验证、content hash chunk_id、不可变索引快照、原子current/previous指针、回滚、BM25、稀疏TF-IDF、RRF、进程缓存）；MCP search_knowledge 已接入真实只读检索，输出来源字段与 `excerptType=paraphrase`。无匹配返回空引用。
- I3 测试：检索/MCP专项10 passed；修复split测试后完整 Agent pytest 21 passed。覆盖索引幂等/版本变更回滚、引用字段、空结果、重复document拒绝、三个策略和dev/holdout切分。
- I3 评测：20张来源卡/20 chunks，100条确定性模板query（80 dev / 20 holdout），三策略各重复3次。最终报告 hybrid overall Recall@1/3/5 0.83/0.97/1.00、MRR 0.8953、P50/P95 2.331/2.735ms；holdout 0.50/0.90/1.00、MRR 0.6808。纯合成标签、未人工核验，不能代表真实语义/诈骗判定性能。数据生成器打印SHA-256与落盘字节校验一致（825c8d6d...6704cd），summary manifest同值；Agent pytest 21 passed。
- I3 source boundary: source content is explicitly paraphrased; no claim that linked 2025/2026 release summaries expose full handbook content. License terms remain unverified; no external publication without rights review.
- I4准备：官方 LangGraph release 页面显示当前 `langgraph-checkpoint-sqlite` patched release 为 3.1.2；官方 advisory 说明 <3.1.2 有 namespace 跨租户问题，3.1.2 已修复；官方 SQLite saver 文档要求对不可信 checkpoint 启用 strict msgpack，并将其定位为轻量/非高并发存储。选择单实例 named-volume SQLite，而非现有 `redis:7-alpine`（Redis saver 依赖额外 RedisJSON/RediSearch 模块）。
- 一次 I4 依赖/接口检查命令从仓库父目录执行导致相对路径不存在；没有文件改动，已记录；后续 agent-service 命令在 `agent-service` 目录运行。
- I4首次专项测试 7 passed / 1 failed：`test_checkpoint_survives_saver_reopen...` 使用 `pytest.raises` 但测试模块未 import pytest；属于测试 harness 缺导入。已记录，下一步补 import 并在 saver 重开后执行合法审核，证明 checkpoint 真正恢复。
- I4接口改造后 Agent 全套 22 passed / 1 failed：唯一失败是既有 `test_failed_detection_is_reported_as_failed_run` patch 旧 `main.run_workflow` symbol；现执行器调用 `main.workflow.run_workflow` 且先停在 WAITING_FOR_REVIEW。属于过期测试桩/预期需随新流程更新，未发现其他失败。
- I4 API专项后续 13 passed / 2 failed：一项为旧测试桩未模拟 checkpointed event 对 run_states 的更新；另一项暴露产品逻辑问题——事件回写后调用 LangGraph `aupdate_state` 使 interrupt 不再可恢复。修复策略是在图状态不写入 callback 状态，依据已持久化的 supplementRound 和暂停类型确定下个 event_seq，并对本地状态单独更新。
- I4序号专项 14 passed / 1 failed：审核恢复后 checkpoint values 保留历史 detection，reporter 错把它再次发为 event_seq=2；需在 reporting 中传递 resume 来源，审核恢复仅上报最终审核结果，补充信息恢复才上报新完成的检测步骤。
