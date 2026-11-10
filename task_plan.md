# 反诈线索研判 Agent 毕设实施计划

## 目标

在已确认题目与边界下，交付可运行的文本线索 Agent 系统、自动化测试、可复现评测脚本和真实跑分报告；全过程按阶段验收，更新 docs/agent-thesis-handoff.md，未实际完成的工作不得勾选或宣称通过。

## 阶段

| 阶段 | 状态 | 完成标准 |
|---|---|---|
| D0 需求确认 | complete | 教师确认题目、个人职责、文本 MVP、测试评测方向和无部署限制 |
| D1 详细设计与自审 | complete | 接口、状态、数据、安全、测试与指标口径成稿；自审结论通过 |
| I1 最小纵向闭环 | in_progress | 经认证用户提交文本；Spring → Agent → 既有 Flask 检测；结构化结果和失败状态可查；契约/集成测试通过 |
| I2 Agent 工作流与 MCP | complete | 工作流节点、白名单 MCP 工具、运行事件与幂等状态回写通过测试 |
| I3 知识检索与引用 | complete | 来源可回查的知识库；BM25 基线及混合检索可切换、可单独评测 |
| I4 暂停恢复与人工审核 | in_progress | 缺项追问、审核、拒绝/退回、checkpoint 持久化及进程重启恢复通过；待完整回归和安全用例 |
| I5 安全、测试与跑分 | pending | 权限、提示注入、故障降级、性能测试；固定数据集评测脚本可复现 |
| I6 交付与论文材料 | in_progress | Compose 部署、操作手册、架构/测试/评测报告、贡献说明与已知限制齐全（部署文档/论文素材已完成，端到端与最终复核待 Docker） |

## 阶段门

- I1 先完成 Flask 检测 API 成功/错误契约，重点确认 error 响应虽带 riskScore=0 仍必须归一为失败且分数为空。
- 新增数据库使用独立版本化非破坏迁移；不得删除 MySQL volume 或重建既有表。
- 前端只能调用 Spring；Agent 与 MCP 私有服务不向宿主机公开业务端口。
- 所有模型/API 密钥从环境读取，不写入仓库；测试默认使用合成/脱敏数据。
- 实测数据以测试脚本产物为准，不填估计值；真实 LLM 未执行时明确写未运行。

## 错误记录

| 错误 | 次数 | 处理 |
|---|---:|---|
| 项目目录不是 Git 仓库，git diff --stat 无法运行 | 1 | 已确认无 .git；后续用文件清单/校验和记录变更，不重复运行同一命令 |
| 首次通过 JS 模板传递 Markdown 代码围栏时触发语法错误 | 1 | 未产生文件修改；去掉围栏后重新应用成功 |
| 创建计划文件时 Markdown 行内反引号未转义，触发 JS ReferenceError | 1 | 未产生文件修改；改用纯文本路径后重试 |
| 更新计划时补丁上下文使用旧版 Next Step 文案，校验失败 | 1 | 未改动文件；重新读取当前文案后按实际内容更新 |
| SQL 标识符反引号打断 JS 模板源码补丁 | 1 | 未写入源码；移除非必要标识符引号后成功应用 |
| Python pytest/asyncio 在受限 Windows 沙箱中卡在 Proactor socketpair 初始化 | 1 | faulthandler 定位到本地 socket accept；中断进程，后续请求沙箱外测试许可或改用 Linux 容器 |
| 第一次 Compose/配置补丁因 .env.template 中 JWT 行与假设不符而校验失败 | 1 | 补丁未落地；按实际模板上下文重试 |
| 相对仓库绝对路径的 apply_patch 审核超时 | 1 | 不假定写入；换用工作区相对路径重试并成功 |
| Maven Surefire 测试阶段在离线模式缺少 junit-platform-launcher 1.7.2 | 1 | 源码和测试源码均编译成功；改为在线依赖解析重试，若网络仍不可用则保留未运行状态 |
| Docker Desktop Linux Engine 未启动，无法启动临时 MySQL | 1 | 未触碰已有卷/容器；迁移脚本的数据库级验证待 Docker 可用后执行 |
| uv pip compile 默认 interpreter cache 被沙箱拒绝写入 | 1 | 未生成锁文件；下一步将 UV_CACHE_DIR 指向 agent-service 工作区内目录重试 |
| uv pip compile 在工作区缓存下仍无法连 PyPI | 1 | 确认本地 socket 网络受限，未生成锁文件；下一步申请沙箱外联网解析，或锁定后采用本地已有依赖做验证 |
| Dockerfile 切换 requirements.lock 的补丁审批超时 | 1 | 不假定写入；重试后成功切换到 hash-checked lock |
| MCP 多文件实现/测试补丁审核超时 | 1 | 复查确认无文件落地；拆成较小补丁逐个应用 |
| 完整 Agent pytest 的沙箱外运行申请审核超时 | 1 | 工具未启动测试进程、无退出码；下一步仅重试一次相同测试 |
| Maven 在线解析依赖时沙箱拒绝写入用户级 .m2 缓存 | 1 | 目标源码编译成功；下一步仅为 Maven 测试申请沙箱外执行，不改项目外其他文件 |
| 记录 Maven/验证结果的计划补丁上下文失效 | 1 | 未改动计划文件；重新核对后追加准确记录 |
| PowerShell 将未加引号的 Maven 多测试类 -Dtest 参数解析为语法错误 | 2 | Maven 未启动；第二次复现后改为 `"-Dtest=A,B"` 整体引号传递，并改用显式 mvn.cmd 路径成功执行 |
| `.\mvnw.cmd` 在 backend 不存在 | 1 | 改用 `D:\Path_Or_Misc\apache-maven-3.9.9\bin\mvn.cmd`，配合 JDK17 运行 Agent 专项测试 12/12 |
| 重启恢复测试把合法恢复断言写在 `pytest.raises` 内 | 1 | 测试假通过；移出异常块后暴露真实缺陷：非法审核先写 checkpoint 导致后续合法恢复失败，已改为入图前校验 |
| Maven 目标测试组发现既有 PasswordEncoderUtilTest.testNullAndEmpty 失败 | 1 | AgentInternalEventControllerTest 2/2、TokenUtilsTest 5/5 通过；该既有失败与 Agent 改动无关，暂不修改，记录为项目基线问题 |
| I2/I3 进度总结补丁误用了旧版 Next Step 文案 | 2 | 校验失败、未改动文件；拆分按实际文件上下文更新 |
| 首次用文件路径启动索引脚本导致 agent_service 不在 sys.path | 1 | Python 未导入应用模块、脚本未生成产物；改用 agent-service 目录下的 python -m scripts.<module> 执行并记录为标准命令 |
| 添加检索评测 split 单测时 apply_patch 审批超时 | 1 | 检查确认补丁未落盘；拆分为小补丁后仅重试一次 |
| Agent 完整 pytest 在受限 Windows 沙箱卡在 asyncio 初始化 | 1 | 中断卡住的沙箱进程后以受控沙箱外 pytest 执行；发现否定自称边界回归并修正，最终全量 27 passed |
| Agent 全量 pytest 暴露否定“没有自称”误识别 | 1 | 将实际命中词纳入否定上下文并全量重测，27 passed；v3 后续仍发现“没有人自称”变体，需放入开发集并另建 v4 holdout |
| 请求沙箱外 Agent 评测时自动审批超时 | 1 | 命令未启动；改为工作区本地沙箱运行离线评测，成功产出 v3 结果 |
| v4 合成数据集大补丁审批超时、模板转义/上下文补丁失败 | 3 | 复核未覆盖项后拆成规则、测试、生成器和评估器小补丁完成；保留失败记录，完整 Agent 测试通过 |
| I4检查命令在项目父目录执行，子目录相对路径未找到 | 1 | 未修改文件或读取敏感数据；已改为仓库根执行，之后运行 Agent 命令固定从 agent-service 目录启动 |
| 新增 checkpoint 重启测试首次运行 NameError: pytest 未导入 | 1 | 专项 7 passed、1 failed；失败在测试模块缺导入，未触及产品断言；修复 import 后重跑，并增加合法审核恢复断言 |
| I4 改造后旧的失败检测 API 测试仍 patch main.run_workflow | 1 | 全套 22 passed、1 failed；执行器已迁为 main.workflow.run_workflow，测试桩和断言仍期待旧的 run.finished 流程；更新成 WAITING_FOR_REVIEW 事件流并重跑 |
| I4 review API 专项发现 paused interrupt 消失 | 1 | Agent API/MCP专项 13 passed、2 failed；根因是 publish 后调用 LangGraph aupdate_state 覆盖挂起任务；改为从持久化 supplementRound + interrupt kind 确定性推导 event_seq，不在暂停点改 checkpoint，再重跑重启和幂等测试 |
| I4 审核恢复把已完成的 readonly_tools 事件再次发出 | 1 | 专项 14 passed、1 failed；恢复后图状态含历史 detection，reporter 把它当本次新步骤；按 resume 来源区分，审核恢复只发 final event，补充恢复才继续报工具步骤 |
| I5 新增负向信息抽取测试时补丁定位不匹配 | 1 | 测试文件未修改；已读取实际函数边界，将测试改为插入到现有工作流测试后 |
| I5 README评测说明补丁上下文不匹配 | 1 | README未修改；将读取文件尾部并按实际段落追加 |
| I5 v3合成数据集大补丁审批超时 | 1 | 首次未报告完成但已部分落地（开发循环数变更）；复核后继续拆补丁完成v3路径和新holdout |
| I5 v3合成数据集小补丁上下文不匹配 | 1 | 重试未修改文件；确认当前为64/16/8/8开发样例与旧holdout，需补齐v3路径、开发负例和新holdout |
| 交接错误记录修订的多文件路径被拒绝 | 1 | 计划文件未修改；已定位文件，后续按单文件更新 |

## Next Step

I6 部署与论文材料已完成：修复 `agent.service` 配置层级、审核参数入图前校验、重启恢复测试假通过；Compose 新卷挂载 V001/V002；部署文档 v2.1 与 `docs/agent-thesis-paper-materials.md` 已产出。复测 Agent 27 passed、Java 专项 12/12、`docker compose config --quiet` exit 0。Docker Engine npipe 仍不存在，MySQL 迁移/Compose 启动/E2E 未验收。Agent v4 与检索结果保持不变，v3/v4 holdout 不得再用于调参。下一步：核查 I3 来源许可、尝试 detector baseline（缺服务则记录 not_run）；Docker 恢复后按部署文档 11.1–11.6 做隔离 MySQL 迁移与端到端验收，再勾 I1/I4/E2E。单轮 LLM、人工核验和成本仍未完成，不得填估计值。
