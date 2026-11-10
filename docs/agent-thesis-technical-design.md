# 反诈线索研判 Agent 系统详细设计

> 版本：0.1  
> 状态：详细设计评审稿  
> 前置依据：指导老师已确认题目、个人边界、文本 MVP、评测方向及部署约束  
> 关联文档：agent-thesis-project-plan.md、agent-thesis-requirements.md

## 1. 设计目标与边界

本设计把“线索录入—已有模型检测—反诈知识检索—生成带依据的研判草稿—人工审核—结果追踪”落成可实现、可测试的系统闭环。重点不是再做一个分类模型，而是构建有状态、可恢复、受控调用工具的 Agent 应用。

设计遵循以下约束：

- 题目保持为“面向电信诈骗线索研判的可控智能体工作流系统设计与实现”。
- 本人新增成果为 Agent 工作流、MCP 工具服务、知识检索与引用、审核续办、运行追踪和评测脚本。
- 现有诈骗检测能力作为被调用工具；室友负责的模型、存证和可视化不写成本人的新增成果。
- MVP 只处理文本线索；不重做语音/图像模型，不加入多 Agent 和自动处置。
- 指标没有预设达标值；先定义口径、运行脚本、保存实测结果，再依据预实验决定优化方向。

## 2. 现有系统依据

- 前端为 Vue，业务后端为 Spring Boot，AI 检测服务为 Python Flask；Docker Compose 已编排 MySQL、Redis、AI 服务、后端和 Nginx。
- 后端已有登录鉴权和文本检测入口。DetectController 的 /detect/text 依赖当前登录用户，并会写入 detection_record。
- 后端 AiServiceClient 已调用 Flask 的 /api/detect/text；MCP 检测工具可复用同一个 Flask 检测能力。
- 当前 MySQL 已有用户、检测记录、证据记录和操作日志表；新增 Agent 表应使用独立表名，不修改既有表语义。
- 既有 AI 服务使用 Python 3.10。新增 Agent/MCP 服务应独立镜像与依赖，避免改变检测服务运行环境；MCP SDK 运行环境按 Python 3.11+ 配置。

### 2.1 集成决策

浏览器只访问 Spring Boot。Spring Boot 负责登录身份、案件归属、用户可见范围、审核人身份和业务数据持久化；Agent 服务和 MCP 工具服务只在 Compose 内网提供服务，不发布浏览器可直接访问的业务端口。

Agent 的文本检测 MCP 工具通过内网调用 Flask 的 /api/detect/text，不调用需要用户 JWT 且会额外写 detection_record 的 /detect/text。Agent 运行本身的调用状态和原始检测结果保存到 Agent 运行记录中。这样既复用已有检测实现，也避免用户令牌传入 Agent 和重复创建检测记录。

现有 Flask 检测接口的错误响应也包含 riskScore=0 和 riskLevel=检测失败，因此 MCP 适配器必须先检查 error 字段；出现 error 时归一为 status=failed、riskScore=null，不得把 0 分当作正常低风险结果。

如果实施时 Flask 接口认证或返回结构与此设计不符，先由 MCP 适配器完成鉴权与字段归一，不修改现有分类模型；接口变化以契约测试验证。

## 3. 总体架构

- Vue 前端：案件录入、研判草稿、来源引用、人工审核、运行轨迹。
- Spring Boot 后端：登录鉴权、案件/运行/审核 API、用户数据隔离、Agent 业务表持久化和审计记录。
- Python Agent 服务（新增、内网）：LangGraph 工作流、节点状态、业务结果校验、MCP Client。
- Python MCP 工具服务（新增、内网）：白名单工具和参数校验。
- 既有 Python Flask 检测服务：由 detect_text_fraud 工具通过内网调用。
- 知识索引：BM25、稀疏 TF-IDF 词项向量与 Reciprocal Rank Fusion (RRF) 混合检索，知识源和段落元数据可回查；当前实现不使用神经语义 embedding。
- SQLite（LangGraph checkpoint）：单实例轻负载下持久化暂停中的工作流；Redis 仍由既有业务服务使用。

调用链为：Vue → Spring Boot（用户 JWT）→ Agent 服务（服务身份）→ MCP 工具服务（内网 MCP）；检测工具再调用 Flask /api/detect/text，知识检索工具查询版本化索引。

运行采用异步受理：Spring Boot 先创建案件/运行记录，再以 run_id 向 Agent 服务提交任务并向前端返回受理状态；Agent 每次状态变化通过内网回调报告事件，Spring Boot 幂等写入 MySQL，前端只读 Spring Boot 的案件/运行数据。Agent 的 SQLite checkpoint 是暂停/恢复依据，Spring Boot 的 MySQL 记录是用户可见状态和审计的业务依据。

### 3.1 部署与信任边界

1. 浏览器不能直连 Agent 服务、MCP 服务、Redis 或 Flask 内部地址；外部请求先经过现有认证和后端权限检查。
2. Spring Boot 到 Agent 服务使用独立服务凭证。凭证放在环境变量或部署密钥中，不进入代码、前端包、日志和论文截图。
3. Agent 服务只接受后端服务身份；MCP 工具只向 Agent 服务开放白名单能力。
4. Agent/MCP 网络访问默认仅限 Compose 内网；AI 服务端口当前若仍需映射到宿主机，应作为现有部署暴露面单独记录，不因此把 Agent/MCP 端口暴露出去。
5. 单节点毕设部署可先按一个 Agent 实例设计；若以后多副本部署，必须先确认 checkpoint 和索引共享存储、并发锁及幂等策略。

## 4. 核心工作流

### 4.1 节点定义

| 节点 | 输入 | 处理与输出 | 失败/分支 |
|---|---|---|---|
| validate_input | 案件文本、来源、补充背景 | 长度/格式校验、敏感信息最小化、生成输入摘要 | 不合法则拒绝，不调用模型 |
| extract_and_check | 合法文本 | 提取事件、主体、渠道、金额/时间等可选字段；判断必需信息是否缺失 | 缺项则生成具体追问并暂停 |
| detect_text | 完整线索 | 通过 MCP 调用既有文本检测，保留原始响应和归一结果 | 超时/不可用记为失败，不生成默认分数 |
| retrieve_knowledge | 线索摘要和关键词 | 调用知识检索，返回带文档/段落定位的 Top-K 片段 | 无命中时显式返回空依据 |
| validate_evidence | 检测结果、检索片段、草稿候选 | 校验引用 ID 来自本次检索结果，输出不混淆事实来源 | 引用无法定位则移除并标为无依据 |
| draft_assessment | 结构化事实、检测响应、引用 | 生成固定结构的研判草稿、待核实问题、建议核查步骤和限制说明 | 输出 Schema 校验失败则有限次重试，仍失败转部分结果/错误 |
| wait_for_review | 研判草稿 | 保存 checkpoint，等待审核动作 | 审核通过、修改、退回或结束 |
| finalize | 审核结果 | 保存最终版本及运行摘要 | 持久化失败时标记可重试错误，不谎报完成 |

### 4.2 执行规则

- 工作流由代码确定流程和允许的分支；模型不能自行创建工具、修改工具白名单或执行任意代码。
- 文本检测和知识检索相互独立时可以并行执行；任一工具失败时保留另一工具结果并生成明确的部分结果。
- 信息补充和人工审核使用可持久化的暂停点。恢复时以案件/运行 ID 定位状态，不将新请求误接到其他案件。
- 每个工具调用均有超时、最大尝试次数、结构校验和可观测状态。对非幂等动作本期不开放；重试只作用于只读查询。
- 运行记录保存“节点、工具、状态、耗时、错误码、结果摘要”等可观察事实，不保存模型隐藏思维链。

### 4.3 状态模型

案件状态：OPEN → RUNNING → WAITING_FOR_INFO → RUNNING → WAITING_FOR_REVIEW → APPROVED；审核退回则进入 REVISION_REQUESTED 后重新运行；工具或流程不可恢复错误进入 PARTIAL 或 FAILED。

运行状态建议为 CREATED、RUNNING、WAITING_FOR_INFO、WAITING_FOR_REVIEW、COMPLETED、PARTIAL、FAILED、CANCELLED。案件状态代表业务生命周期，运行状态代表单次执行；新一轮运行生成新的 run_id，不能覆盖旧运行结果。

## 5. API 契约草案

所有面向浏览器的接口沿用 Spring Boot 现有鉴权与统一 Result 响应格式。路径为相对现有后端根路径的建议路径；正式实现前与当前前端路由、全局前缀统一。

### 5.1 用户侧 Spring Boot API

| 方法与路径 | 用途 | 请求关键字段 | 成功响应关键字段 |
|---|---|---|---|
| POST /agent/cases | 创建案件 | content、source、context | caseId、caseNo、status |
| GET /agent/cases/{caseId} | 查看案件及最新状态 | 无 | case、latestRun、review |
| GET /agent/cases | 按当前用户分页查询 | page、pageSize、status | items、total |
| POST /agent/cases/{caseId}/runs | 开始新一轮研判 | 可选 reason | runId、status |
| GET /agent/runs/{runId} | 查询运行结果和可观察轨迹 | 无 | status、draft、citations、steps、errors |
| POST /agent/runs/{runId}/resume | 补充信息并恢复 | supplement | runId、status |
| POST /agent/runs/{runId}/review | 提交人工审核 | action、comment、editedDraft | status、reviewId |

安全要求：

- caseId/runId 不是权限凭证；每次读取和修改都必须按 TokenUtils 当前用户及案件归属查询。
- 审核接口另外检查审核权限；仅有案件读取权限不代表有审核权限。
- 输入做长度、类型和字段白名单校验；数据库写入使用参数化查询。
- 长耗时运行建议先返回受理状态，前端通过轮询 GET 查询；轮询间隔和总超时由实现配置确定。
- 任何错误响应不得包含内部凭证、完整堆栈或模型隐藏思维链。

### 5.2 Spring Boot 到 Agent 私有 API

| 方法与路径 | 用途 | 关键字段 |
|---|---|---|
| POST /internal/v1/runs | 创建/执行一次工作流 | runId、caseId、ownerId、content、context、configVersion |
| POST /internal/v1/runs/{runId}/resume | 续接补充信息或审核动作 | action、payload、actorId |
| GET /internal/v1/runs/{runId} | 后端查询当前状态与结果 | status、draft、citations、steps、errorCode |
| POST /internal/v1/runs/{runId}/events | Agent 状态回调到后端 | eventSeq、eventType、status、step、occurredAt |

私有 API 使用独立服务凭证，并限制来源为后端容器网络。Agent 服务不接受浏览器 JWT 作为自身授权方式；ownerId 只作为后端传入的关联字段，不由模型生成。重复提交相同 runId 必须幂等：返回已有运行，不重复启动第二个图执行。resume 请求另带 actionId，重复 actionId 不重复恢复。

事件至少一次投递，使用 run_id + event_seq 去重。后端仅接受比当前 last_event_seq 更新的事件推进运行状态；旧事件可记录但不能回退状态。回调失败时 Agent 有限次重试，后端对持续 RUNNING/事件序号异常的运行定时通过私有 GET 状态接口与 Agent checkpoint 对账。用户 GET 始终以 MySQL 已确认状态为准；Agent 不可用时仍可查看最后一次已持久化状态。

### 5.3 MCP 工具契约

| 工具名 | 输入 | 输出 | 限制 |
|---|---|---|---|
| detect_text_fraud | content、可选 model | status、riskScore、riskLevel、detail、rawFields、latencyMs | 仅调用既有文本检测；文本长度受限；失败用 errorCode 表达，不伪造 0 分 |
| search_fraud_knowledge | query、topK、可选 category | hits[]：docId、chunkId、title、publisher、sourceUrl、publishedAt、snippet、score、indexVersion | topK 有上限；只读；无命中返回空数组 |

工具输入输出均有 JSON Schema。MCP 服务拒绝未知工具、额外危险字段、超限文本和超出 topK 上限的请求。工具错误采用可判定类别，例如 INVALID_ARGUMENT、UPSTREAM_TIMEOUT、UPSTREAM_UNAVAILABLE、NO_MATCH；对用户显示可理解提示，对内部记录错误码和耗时。

## 6. 数据模型与持久化

Agent 业务数据与既有 detection_record、cert_record 分表管理，不修改室友负责模块的数据语义。

| 建议表 | 主要字段 | 用途/约束 |
|---|---|---|
| agent_case | id、case_no、user_id、status、source、content_ref、created_at、updated_at | 案件主记录；case_no 唯一；user_id 建索引 |
| agent_run | id（数据库主键）、run_id（UUID 唯一）、case_id、status、graph_thread_id、last_event_seq、config_version、input_hash、started_at、finished_at、summary_json | 每次独立运行；case_id/status 建索引 |
| agent_event | id、run_id、event_seq、event_type、status、payload_json、occurred_at、received_at | 状态回调幂等依据；run_id + event_seq 唯一 |
| agent_step | id、run_id、step_name、tool_name、status、attempt、duration_ms、error_code、input_summary、output_json、created_at | 运行轨迹；不保存思维链；按 run_id/时间查询 |
| agent_review | id、run_id、reviewer_id、action、comment、edited_draft_json、created_at | 审核记录不可被新运行覆盖 |
| knowledge_document | id/doc_id、title、publisher、source_url、published_at、version、content_hash、status | 知识来源、版本和许可/停用状态 |
| knowledge_chunk | id/chunk_id、doc_id、chunk_index、content、metadata_json | 文档切片及可回查定位；doc_id 建索引 |

案件/运行 ID、数据库主键和 graph_thread_id 是不同字段，不复用或从用户输入推导。新增表通过独立的、版本化且可重复检查的迁移脚本创建；docker-compose 当前挂载的 anti_fraud.sql 只会在 MySQL 空数据目录初始化时执行，不能把新增表只写进初始化脚本后就假设已有库会升级。既有数据卷先备份，再运行非破坏性迁移；禁止为升级而删除数据库卷或重建既有表。

索引方案采用 BM25 关键词检索、稀疏 TF-IDF 词项向量检索与 Reciprocal Rank Fusion (RRF) 混合排序。当前实现从带来源元数据的 JSONL 知识卡生成确定性 chunk_id 和不可变 JSON 索引快照，以 SHA-256 派生 index_version，通过 current/previous 指针原子切换并支持回滚；运行期缓存快照与分词结果。索引支持字段包含 source_id、document_id、版本、发布方、URL、日期、段落定位及许可复核状态。当前不使用神经 embedding，亦未声称语义检索能力；如后续增加稠密向量模型，应作为独立变量升级并单独跑分。

工作流 checkpoint 使用安全版本的 LangGraph AsyncSqliteSaver，以 run_id 作为 thread_id，文件位于持久卷；`LANGGRAPH_STRICT_MSGPACK=true`。这是单 Agent 实例、轻负载毕设部署方案，不适用于多副本或生产级并发写入。暂停期间 checkpoint 包含原始及补充线索，须按敏感数据管理；Agent 在最终事件被后端确认后删除该 run 的 checkpoint，审核、事件和最终草稿由 MySQL 保存。等待补充/审核的 checkpoint 不自动过期，运维需制定卷备份、访问控制和保留期限；丢失卷会使未完成运行无法恢复。

### 6.1 输出结构

研判草稿至少包含以下字段：

| 字段 | 内容 | 来源约束 |
|---|---|---|
| caseId、runId、status | 业务及运行标识 | 后端生成 |
| summary | 线索摘要 | Agent 生成并明确标注为摘要 |
| extractedFacts | field、value、source 列表 | source 只能为 user_input、detector、knowledge 或 agent_summary |
| detection | status、riskScore、riskLevel、detail、toolCallId | 失败时 status=failed，score 为空，不能用 0 代替失败 |
| citations | docId、chunkId、title、publisher、sourceUrl、publishedAt、quote | 只能引用本次检索命中并可回查的片段 |
| missingInformation | 仍需补充的信息列表 | 由规则/结构化抽取结果产生 |
| suggestedChecks | 建议人工核查步骤 | 仅建议，不触发外部副作用 |
| uncertaintyNotes、reviewStatus | 不确定性和审核状态 | 明确区分模型判断与人工确认 |

模型输出经 JSON Schema 校验后才入库和展示；引用 ID 不在检索结果中的草稿不得通过校验。

## 7. 安全、隐私与可靠性

- 线索和检索材料均视为不可信输入；提示注入内容不得改变工具权限、系统规则或数据访问范围。
- 对话原文只在完成业务所需范围内保存；数据库、checkpoint、日志和评测集使用脱敏或合成内容，日志默认保存摘要与哈希而非完整原文。
- 对工具响应做字段白名单归一，避免把外部服务的任意内容解释成控制指令。
- 检测接口超时、格式异常、模型服务错误、知识库不可用分别记录；检测结果未知与低风险严格区分。
- 对只读工具做有限次重试与指数退避；重试耗时计入端到端时延，重试次数写入轨迹。
- 使用请求 ID/run_id 关联后端、Agent、MCP 和 AI 服务日志；日志中不得记录密钥。
- 对用户可见错误采用稳定错误码与短说明；原始异常留在受控日志并做敏感字段清理。
- 评测知识库只使用许可清晰的公开材料或自编合成内容，记录来源、抓取日期、许可和内容哈希。

## 8. 测试设计

### 8.1 测试层级

| 层级 | 重点用例 | 验收证据 |
|---|---|---|
| 单元测试 | 输入校验、字段抽取/归一、状态转换、引用 ID 校验、错误映射、Schema 校验 | 自动化测试通过记录 |
| MCP 契约测试 | 工具名称、参数边界、响应结构、未知工具拒绝、超时错误映射 | 契约测试报告 |
| 工作流集成测试 | 正常闭环、缺项暂停/补充恢复、审核暂停/通过、退回后续办 | 状态迁移断言和运行轨迹 |
| 故障注入测试 | 检测服务超时、知识检索无结果、Redis/checkpoint 短暂不可用、模型无效 JSON | 失败可见、部分结果正确、无伪造分数/引用 |
| 安全测试 | 提示注入、越权 caseId/runId、非法工具参数、敏感日志扫描 | 注入不能扩权、越权拒绝、日志无敏感凭证 |
| 端到端测试 | 登录后创建案件至审核完成；检查前端数据与后端记录一致 | 可重复演示和自动化报告 |
| 性能测试 | 固定数据、固定并发档位，测端到端与各节点耗时 | P50/P95、错误率、环境和配置记录 |

LLM 输出存在非确定性。单元和集成测试优先用确定性模型桩/固定工具响应；真实模型评测另行执行，并保存模型名、提示版本、参数、日期和数据集版本。这样避免每次 CI 因模型随机输出而不稳定。

## 9. 离线评测与可运行跑分

### 9.1 数据集

建立约 100–200 条经人工核验的脱敏或合成场景，覆盖正常、信息缺项、多轮补充、模糊/矛盾线索、知识无匹配、工具故障、提示注入。每条样例包含 case_id、输入、类别、必需抽取字段、预期动作、允许工具、gold 文档/段落 ID 和审核判定要点。按固定版本保存，划分开发集与留出测试集，避免用留出集反复调提示词。

### 9.2 对照组和优化组

| 方案 | 定义 | 主要比较目标 |
|---|---|---|
| B0 现有检测 | 只调用既有文本检测接口 | 现有模型基线和调用时延 |
| B1 单轮 LLM | 同一模型基于同一线索直接生成摘要，不接工具/知识库 | 无编排生成基线 |
| E1 Agent 基线 | 固定工作流 + 检测工具 + BM25 检索 | Agent 工具编排与证据引用能力 |
| E2 Agent 优化 | 同一工作流 + BM25、稀疏 TF-IDF 与 RRF 混合检索 | 与 E1 比较检索策略收益；神经 embedding/reranker 若加入则作为独立实验变量 |

检索优化单独跑分：BM25、稀疏 TF-IDF 词项向量、RRF 混合召回分别使用同一查询集和同一知识索引版本，报告 Recall@K、MRR、检索耗时；再比较引用支持准确率。当前合成查询集并非人工核验，跑分只用于工程回归与初步策略比较，不能据此声称真实语义相关性。每次实验固定其余模型、提示、数据和索引版本；任何神经 embedding/reranker 若加入则独立报告，不能与混合召回一并宣称为单一优化收益，不作为 MVP 前置条件。

### 9.3 指标口径

| 指标 | 计算口径 |
|---|---|
| 工作流完成率 | 正常完成或按预期暂停的样例数 / 总样例数；预期暂停算正确完成流程，不等同于案件结案 |
| 关键信息抽取 F1 | 对人工标注字段计算 micro Precision、Recall、F1；明确空值和不适用字段口径 |
| 工具选择准确率 | 实际调用工具集合与 gold 工具集合完全一致的样例数 / 总样例数 |
| 参数有效率 | Schema 校验通过的工具调用数 / 工具调用总数 |
| 引用 Recall@K / MRR | 检索结果中命中 gold 段落的比例及其倒数排名均值 |
| 引用可追溯率 | 带有有效 docId/chunkId 且能定位来源的引用数 / 输出引用总数 |
| 引用支持准确率 | 人工判断引用片段支持其对应陈述的引用数 / 抽检引用总数 |
| 正确降级率 | 工具故障时正确标注失败/部分结果且未编造分数或依据的样例数 / 故障样例总数 |
| 安全拦截率 | 越权工具调用、提示注入扩权和跨用户读取均被阻止的测试数 / 对应安全测试总数 |
| 输出结构有效率 | 满足输出 JSON Schema 的结果数 / 总结果数 |
| 时延与成本 | 报告端到端 P50/P95、分节点耗时；可获得 token/价格时按运行日期计算成本并注明价格来源 |

不得将不同维度压成未经论证的单一总分。论文同时给出样例数、数据版本、置信范围或抽样说明、失败样例及人工复核方法。若外部模型服务不可用，仍可运行确定性单测、MCP 契约测试、检索评测和使用模型桩的端到端测试；真实 LLM 指标标记为未运行，不能伪造。

### 9.4 评测脚本约定

建议新增独立 eval 目录，不与生产 API 混在一起。命令接口可按以下形式实现，参数名以代码实现时为准：

- python -m eval.run --dataset eval/datasets/holdout.jsonl --variant all --output eval/reports
- python -m eval.run --dataset eval/datasets/holdout.jsonl --variant retrieval --retriever hybrid
- python -m eval.run --dataset eval/datasets/holdout.jsonl --variant workflow --model-stub

每次运行在唯一时间戳目录输出：

- summary.json：各方案指标、样本数、数据/索引/提示/模型版本、运行环境和聚合耗时。
- cases.jsonl：逐样例预期值、实际值、判定结果、工具轨迹和失败原因；对敏感输入只保留脱敏 ID 或哈希。
- report.md：自动生成的可读对比表、实测差异、失败样例摘要和运行命令。
- manifest.json：数据集哈希、索引版本、代码版本、模型配置及开始/结束时间。

优化结论只能由脚本实际生成的数据支持。每个改动先在开发集选择参数，再固定参数跑留出集；报告原始值与差值，不把开发集调参结果当作泛化结论。

## 10. 迭代实施顺序与阶段门

| 阶段 | 主要交付 | 进入下一阶段的条件 |
|---|---|---|
| D0 需求确认 | 已确认的题目、范围、角色、验收场景和评测方向 | 本阶段已完成 |
| D1 详细设计 | 本文接口、状态、数据、安全和评测口径；团队确认复用接口 | API 字段和调用边界评审通过 |
| I1 最小纵向闭环 | 一个文本线索经 Spring → Agent → 既有检测 → 结构化结果返回 | 成功、失败、越权三类路径都有测试 |
| I2 MCP 工具与轨迹 | 检测工具和知识搜索工具，结构化运行步骤 | MCP 契约测试和错误映射通过 |
| I3 RAG 与引用 | 文档导入、分段、索引、来源展示与无结果处理 | 引用 ID 可回查；检索脚本可跑分 |
| I4 暂停恢复与审核 | 缺项暂停、人工审核、SQLite checkpoint 恢复 | Agent 进程重启后的续办验证通过 |
| I5 测试评测 | 自动化测试、留出数据跑分和报告 | 指标脚本能复现；结果有失败样例与配置清单 |
| I6 安全与交付 | 权限隔离、脱敏、部署文档、答辩演示和论文材料 | 完成需求验收并列清已知限制 |

每个实现阶段按“接口/验收先行 → 单个端到端切片 → 自动化验证 → 记录实测结果 → 决定下一步”推进。当前已有 Agent/MCP、检索和可恢复审核实现；MySQL 环境级迁移与完整端到端验收仍需 Docker Engine。

## 11. 待设计评审确认的实现细节

以下不影响总体设计，但编码前需结合项目现状做小范围验证：

1. Spring Boot 现有全局路由前缀、统一 Result 字段及分页参数约定。
2. Flask 文本检测请求/响应的实际 JSON Schema、鉴权方式和超时行为；由 MCP 适配器契约测试固定。
3. LangGraph SQLite checkpoint 单实例部署边界、strict msgpack 配置和暂停运行的敏感数据保留；通过进程重启恢复测试验证。
4. 反诈知识材料清单、授权/许可、来源字段和文档更新方式。
5. 现有用户角色能否区分研判与审核；如不能，先采用明确的演示账号/角色配置，不弱化归属校验。
6. 当前项目未检出 Flyway/Liquibase 迁移工具，且 MySQL 初始化 SQL 只对空数据目录执行；实现前确定独立版本化迁移脚本和升级说明。
7. 当前项目的统一前端组件、API 分页和错误提示约定；新增接口按现有约定落地。

## 12. 自审结论

**结论：详细设计通过，可进入 I1 最小纵向闭环。**

评审发现并已在本文修正以下风险：Agent 异步状态与 Spring/MySQL 之间缺少回写协议；既有 Flask 错误响应携带 0 分可能被误判为低风险；现有数据库初始化脚本不会自动升级已有数据卷；检索优化对照需一次只改变一个变量。

进入 I1 前置检查：

- 用契约测试确认 Flask /api/detect/text 的输入、成功响应和 error 响应；error=true 时归一分数必须为空。
- 确认 Agent 异步事件的 run_id/event_seq 幂等回写、超时和重试路径。
- 新增表使用独立迁移，不删除或重建现有数据库卷。
- I1 仅验证文本纵向闭环与结构化结果，不提前实现尚未到阶段的知识库、审核页面和跑分报告。

评审仅批准设计进入下一阶段，不代表功能已经实现或性能、安全指标已经通过。

## 参考资料

- LangGraph Interrupts：暂停、保存状态并恢复执行，https://docs.langchain.com/oss/python/langgraph/interrupts
- LangGraph Persistence：线程状态与持久化，https://docs.langchain.com/oss/python/langgraph/persistence
- Model Context Protocol Python SDK：https://py.sdk.modelcontextprotocol.io/
