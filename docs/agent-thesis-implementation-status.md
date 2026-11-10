# Agent 毕设需求追踪矩阵

本矩阵区分“代码已实现”“自动测试通过”和“环境级端到端验收”。仅勾选已由对应证据支持的内容；未运行的数据库或真实模型场景不推定通过。

| ID | 能力/验收点 | 实现位置 | 验证证据 | 状态 |
|---|---|---|---|---|
| AG-01 | 受控 Agent 私有入口、服务鉴权、请求幂等 | `agent-service/agent_service/main.py` | `agent-service/tests/test_api.py`、`agent-service/tests/test_mcp_workflow.py` | 单测通过；生产容器端到端待验 |
| AG-02 | 白名单只读 MCP 工具、schema、超时和轨迹 | `agent-service/agent_service/mcp_tools.py`、`mcp_client.py` | `agent-service/tests/test_mcp_workflow.py` | 通过 |
| AG-03 | 固定 LangGraph 文本检测与结果草稿 | `agent-service/agent_service/workflow.py` | `agent-service/tests/test_mcp_workflow.py` | 通过；无真实 LLM 生成 |
| DB-01 | 案件/运行/事件及补充/审核 Spring 持久化与数据库迁移 | `sql/migrations/V001__agent_core.sql`、`V002__agent_human_review.sql`、`backend/src/` | `AgentRunServiceTest`、`AgentInternalEventControllerTest` | Java 专项测试通过；临时 MySQL / 迁移 / 全链路待 Docker Engine |
| DET-01 | Flask 错误响应不能被映射为低风险 0 分 | `agent-service/agent_service/detector.py` | `agent-service/tests/test_detector.py::test_detect_text_treats_flask_error_score_zero_as_failure` | 通过 |
| KB-01 | 来源清单、许可状态、确定性 chunk_id 和版本索引 | `agent-service/data/knowledge_sources.jsonl`、`agent-service/agent_service/retrieval.py` | `agent-service/tests/test_retrieval.py` | 实现/单测通过；来源许可未独立核验 |
| KB-02 | BM25、稀疏 TF-IDF、RRF、版本切换/回滚 | `agent-service/agent_service/retrieval.py` | `agent-service/tests/test_retrieval.py` | 通过；不含神经 embedding |
| KB-03 | 可回查引用；转述标识；无匹配不造引用 | `agent-service/agent_service/mcp_tools.py`、`retrieval.py` | `test_retrieval.py`、`test_mcp_workflow.py` | 通过 |
| EVAL-01 | 100 条检索 query、dev/holdout、三策略指标与产物 | `agent-service/scripts/`、`agent-service/data/retrieval_eval.jsonl` | `agent-service/eval/results/latest/` | 已运行；合成模板集、未人工核验 |
| HITL-01 | 缺项追问、可恢复 checkpoint、审核通过/修改/退回 | `agent-service/agent_service/workflow.py`、`main.py`、Spring `AgentRunService` | Agent pytest 27/27；Java `AgentInternalEventControllerTest,AgentRunServiceTest` 12/12；非法审核字段在写检查点前拒绝，随后合法恢复通过 | 代码/API/SQLite saver reopen 单测通过；真正进程重启及 MySQL 联调待验 |
| UI-01 | Vue 案件提交流程、引用/轨迹和人工审核界面 | `frontend/src/views/agent/AgentWorkspace.vue`、`frontend/src/components/agent/` | `npm run build` 通过 | 已实现并构建；浏览器端到端和后端联调待验 |
| EVAL-02 | Agent workflow v4 120-case benchmark (96/24), outputs and holdout metrics | `agent-service/scripts/create_agent_eval_dataset.py`, `evaluate_agent.py`, `agent-service/data/agent_eval_v4.jsonl` | `agent-service/eval/agent/v4/` report, manifest, per-case outputs; 50 repeats; 0 mismatch | 本地确定性规则/fixture 测试通过；数据仍未人工核验，不是诈骗识别准确率；live baselines not run |
| DEP-01 | Agent 服务配置、密钥、迁移、检查点备份与回滚文档 | `application.yml`、`application-prod.yml`、`docker-compose.yml`、`docs/部署文档.md` | 配置根节点修复；Compose 新卷挂载 V001/V002；`docker compose config --quiet` 通过；文档 v2.1 | 配置与文档就绪；容器级启动/迁移仍未验收 |
| E2E-01 | 前端至 Spring、Agent、MCP、Flask、MySQL 全链路 | Spring、Agent、MCP、Flask、Vue 和 MySQL migrations | Docker Engine unavailable (`dockerDesktopLinuxEngine` npipe missing); no E2E run | 未验收；未触碰既有容器或 volume |

## 当前 I3 跑分

运行命令（当前工作目录为 `agent-service`）：

```powershell
.\.venv\Scripts\python.exe -m scripts.build_knowledge_index
.\.venv\Scripts\python.exe -m scripts.create_retrieval_dataset
.\.venv\Scripts\python.exe -m scripts.evaluate_retrieval --repeats 3
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

2026-10-26 本地实测，索引版本 `1cae7be40108f26f`，100 条模板合成查询，20 个来源卡，每 query 3 次计时：

| Strategy | Split | Recall@1 | Recall@3 | Recall@5 | MRR | P50 ms | P95 ms |
|---|---|---:|---:|---:|---:|---:|---:|
| BM25 | all | 0.7800 | 0.9600 | 1.0000 | 0.8673 | 2.339 | 2.662 |
| TF-IDF | all | 0.8100 | 0.9800 | 1.0000 | 0.8895 | 2.332 | 2.718 |
| Hybrid | all | 0.8300 | 0.9700 | 1.0000 | 0.8953 | 2.331 | 2.735 |
| BM25 | holdout (20) | 0.2500 | 0.8500 | 1.0000 | 0.5517 | 2.440 | 2.774 |
| TF-IDF | holdout (20) | 0.5000 | 0.9000 | 1.0000 | 0.6808 | 2.505 | 2.813 |
| Hybrid | holdout (20) | 0.5000 | 0.9000 | 1.0000 | 0.6808 | 2.500 | 2.854 |

Holdout Top-1/MRR 说明基于模板的当前数据仍不足以支持高质量语义检索结论；Top-5=1.0 主要受小知识库规模影响。结果只衡量来源卡检索，不是诈骗识别准确率、人工引用支持率或线上性能。论文实验前应由人工复核查询与 gold 文档，并扩充真实但脱敏的表达变体。
