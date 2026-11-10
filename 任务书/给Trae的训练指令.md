# 给 Trae 的任务指令：训练文本诈骗检测模型

> 使用方法：丙同学把本文件**全部内容**复制给 Trae 对话框，Trae 会按指令完成训练并产出可提交的文件。
> 工作目录：`AI_Anti_fraud_Software/ai-service/`

---

## 复制线以下内容给 Trae ↓↓↓

你是我的 Python 机器学习工程师。请在当前项目的 `ai-service/` 目录下完成文本诈骗检测模型的训练任务。项目已有完整的三层融合检测架构（规则层 + LLM 层 + 本地模型层），本地模型层权重缺失，你的任务是把模型训出来。**不要修改 `anti_fraud_text.py` 里的三层融合逻辑和模型加载文件名约定。**

### 一、数据集情况（已确认，直接使用）

数据集已下载并解压，位于 `ai-service/data/raw/Telecom_Fraud_Texts_5-main/`（如果你看到的路径不同，自行用 Glob 查找 `label0*-last.csv`）：

| 文件 | 条数 | label 列原始值 | 含义 |
|------|------|--------------|------|
| label00-last.csv | 7838 | `0` | 正常文本（运营商营销短信等） |
| label01-last.csv | 1000 | `冒充公检法及政府机关类` | 诈骗 |
| label02-last.csv | 1000 | `贷款、代办信用卡类` | 诈骗 |
| label03-last.csv | 1000 | `冒充客服服务` | 诈骗 |
| label04-last.csv | 1000 | `杀猪盘类`（恋爱诱导投资类） | 诈骗 |

每个 CSV 两列，表头为 `content,label`，总计约 11838 条。

**两个已确认的坑，必须处理：**

1. **编码不一致**：`label04-last.csv` 是 GBK 编码（用 UTF-8 读会乱码/报错），其余是 UTF-8。读文件时必须按"utf-8-sig → gbk"顺序尝试，不要假设统一编码。
2. **标签要映射**：本次先做**二分类**：label 为 `0` 的映射为 `0`（正常），其余 4 类全部映射为 `1`（诈骗）。同时保留一列 `category` 存原始中文类别，方便以后做多分类。

### 二、具体任务

**任务1：编写 `scripts/prepare_dataset.py`**

- 读取上述 5 个 CSV（编码自动兼容）
- 清洗：去除 content 为空/纯空白的行、按 content 去重、去除超长文本（>500字截断或丢弃，你决定并在报告里说明）
- 标签映射：二分类 label（0/1）+ 保留 category 原始类别列
- 分层抽样按 8:1:1 切分 train/val/test（`random_state=42`，保证可复现，按 label 分层）
- 输出到 `data/text/processed/train.csv`、`val.csv`、`test.csv`（表头 `content,label,category`）
- 脚本末尾打印每个文件的条数、正负样本比例、各类别分布
- 把数据集自带的 `LICENSE`（GPLv3）保留在 `data/raw/` 中，不要删除

**任务2：运行数据准备脚本，确认输出正常。**

**任务3：训练传统基线模型**

运行 `python scripts/train_text_baseline.py`（TF-IDF n-gram + LinearSVC）。
先读一遍该脚本，确认它读取的列名、路径与任务1的输出一致；不一致就**修改训练脚本适配**（不要改数据输出格式去迁就脚本），最终产物文件名必须是 `models/text_baseline.joblib`（这是 `anti_fraud_text.py` 加载时写死的名字）。

**任务4：训练深度模型**

运行 `python scripts/train_text_bilstm.py`（BiLSTM+Attention），产出 `models/text_bilstm.pt` 及配套词表/配置 JSON（文件名遵循脚本现有约定，不要改）。
本机是 CPU 训练，如果预估超过 2 小时，把 epochs 降到 15、batch_size 设 16，并在报告里说明实际使用的超参数。

**任务5：评估并生成报告**

在 test 集上评估两个模型，产出 `reports/text_model_report.md`，包含：

- 数据集说明（来源、总量、清洗后数量、类别分布、切分比例）
- 两个模型各自的：accuracy、precision、recall、F1（正负类分别给出）、混淆矩阵（图存 `reports/confusion_matrix_baseline.png` 和 `confusion_matrix_bilstm.png`）
- 实际使用的超参数、训练耗时、运行环境（CPU/GPU、主要依赖版本）
- 结论：哪个模型作为线上主模型

验收硬指标（达不到要在报告里分析原因并尝试调参，不许造假）：
- 测试集 accuracy ≥ 85%
- 诈骗类（label=1）recall ≥ 90% —— 反诈场景宁可误报不可漏报

**任务6：端到端验证**

重启 Flask 服务（`cd flask_app && python app.py`），用以下文本验证三层融合链路正常：

- `需要提前缴纳培训费10000元才能办理入职` → 期望高风险
- `我们养老院可以免费接收老人抚养，请填写身份相关信息` → 期望高风险
- `明天下午三点组会记得带上周的报告` → 期望低风险/无风险
- `您的快递已放驿站，取件码6-2-3018` → 期望低风险

把 4 条的实际返回 JSON 记录到报告里。

### 三、Git 提交规则（重要，别乱 push）

仓库 `.gitignore` 已忽略 `*.joblib`、`*.pt`、`**/data/*.csv`，所以：

1. **正常提交**：`scripts/prepare_dataset.py`、训练脚本的改动、`reports/` 下的报告和图片（放 reports/ 目录，不被忽略）、`data/raw/LICENSE`
2. **原始数据 CSV**（仅 3.6MB，很小）：用 `git add -f` 强制添加 `data/raw/Telecom_Fraud_Texts_5-main/` 下的 5 个 CSV
3. **模型权重不要自己强行 push**：先跑 `git check-attr` / 查看文件大小，把 `text_baseline.joblib`、`text_bilstm.pt` 的**文件大小**写进报告，然后停下来告诉我（人类），由我决定用 Gitee LFS 还是发行版附件上传。不要自行使用 git filter-branch 或 force push。
4. commit message 用中文写清楚，例如：`feat(ai): 新增数据集准备脚本并完成文本模型训练(acc=xx%)`

### 四、环境

- 缺依赖先装：`pip install scikit-learn pandas numpy joblib jieba`（BiLSTM 还需要 `torch`，装 CPU 版即可）
- 每一步执行命令后检查输出，报错就修复，不要跳过失败步骤假装成功
- 全部完成后，给我一份总结：最终指标、产出文件清单、模型文件大小、有没有未解决的问题

## 复制线以上内容给 Trae ↑↑↑

---

## 给丙同学本人的备注（不用发给 Trae）

- 数据集来源：Telecom_Fraud_Texts_5（GPLv3 许可，论文里引用要注明出处）
- 跑完后把模型文件大小发给后端负责人，决定权重分发方式
- 训练卡住或指标不达标，当天在群里同步，不要自己闷头调超过一天
