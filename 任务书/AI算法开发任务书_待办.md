# AI 算法开发任务书（待办版）

> 更新日期：2026-10-11　|　对接人：后端负责人
> 本文档基于项目当前最新状态编写，**请以此为准**，旧的 AI 算法任务书中已完成的部分不再重复。
> 训练部分已写成手把手教程，照着做即可，卡住了当天在群里问。

---

## 一、项目现状（你需要知道的）

文本检测已升级为**三层融合架构**：

| 层 | 文件 | 状态 |
|----|------|------|
| ① 规则层（关键词+正则） | `ai-service/anti_fraud_text.py` | ✅ 已完成 |
| ② LLM 语义层（DeepSeek API） | `ai-service/llm_detector.py` | ✅ 已完成（能识别词库外新话术） |
| ③ 本地模型层（TF-IDF+SVM / BiLSTM） | `models/text_baseline.joblib`、`models/text_bilstm.pt` | ❌ **权重缺失，未训练** ← 你的核心任务 |
| 语音检测 | `anti_fraud_voice.py` | ⚠️ 骨架已有，模型未训 |
| 图像检测 | `anti_fraud_image.py` | ⚠️ 骨架已有，OCR 未接 |
| 多模态融合 | `risk_assessment.py` | ⚠️ 代码已有，`models/fusion_model.joblib` 缺失 |

> 三层融合逻辑已接好（取最高分），你**只需要把模型训出来放进 `models/` 目录**，服务重启自动生效，不用改任何融合代码。

---

## 二、P0：文本模型训练（手把手教程）

### 总览：工作量90%在数据，训练只要几条命令

| 环节 | 耗时 | 难度 |
|------|------|------|
| 下载+整理数据集 | 1-2天 | ⭐⭐⭐ 真正的瓶颈 |
| 预处理 | 几分钟 | ⭐ 脚本现成 |
| TF-IDF+SVM 训练 | 3-10分钟（CPU） | ⭐ 一条命令 |
| BiLSTM 训练 | CPU 1-2小时 / 独显 10-20分钟 | ⭐ 挂机跑 |

**策略：先训 TF-IDF+SVM（几分钟出结果，准确率就能到85%左右），立刻跑通全流程；BiLSTM 第二天睡前挂机训。别一上来就调参。**

### 第1步：获取数据集（唯一费时间的环节）

用公开数据集，**不要自己手工标注**：

| 数据集 | 获取方式 | 说明 |
|--------|---------|------|
| **CCL2023 电信诈骗文本识别数据集** | 搜索"CCL2023 诈骗文本 数据集"，天池/CCL官网申请下载 | 约1万+条，**首选** |
| 360安全社区/腾讯安全管家博客的诈骗话术合集 | 网页复制整理 | 补充各类话术 |
| 正常文本（负样本） | 短信/聊天记录脱敏样本，或让 LLM 批量生成日常对话 | ≥30% 占比，防止模型把所有消息都判成诈骗 |

**数据格式要求** —— 最终整理成 CSV，两列，UTF-8 编码：

```csv
text,label
"恭喜您被抽中为幸运用户，请点击链接领取奖品",1
"您的快递已到驿站，取件码8837",0
"需要先缴纳培训费10000元才能入职",1
"妈妈明天下午回家吃饭",0
```

- `label`：1=诈骗，0=正常
- 总量 **≥ 5000 条**（train/val/test = 8:1:1，`preprocess_text.py` 自动切分）
- 覆盖诈骗类型：刷单返利、虚假投资、冒充公检法、冒充客服、虚假贷款、**求职缴费类**、**个人信息收集类（养老/补贴骗局）**、中奖诈骗、钓鱼链接、冒充熟人
- 每类至少 200 条；正常文本 ≥ 1500 条

### 第2步：放好数据

```
ai-service/
└── data/
    └── text/
        └── processed/
            ├── train.csv    ← 全部数据放这一个文件也行，脚本会自动切
            └── (val/test 由脚本自动生成)
```

### 第3步：预处理

```bash
cd C:\Users\BQY\Desktop\HomeWork\AI_Anti_fraud_Software\ai-service
python scripts\preprocess_text.py
```

成功标志：`data/text/processed/` 下生成 `train.csv`、`val.csv`、`test.csv`。

### 第4步：训练

```bash
# 先训传统模型（3-10分钟出结果）
python scripts\train_text_baseline.py

# 再训深度模型（CPU约1-2小时，睡前挂机；默认 epochs=30, batch=32，有NVIDIA显卡自动用GPU）
python scripts\train_text_bilstm.py
```

产出：
- `models/text_baseline.joblib`（TF-IDF + LinearSVC）
- `models/text_bilstm.pt`（BiLSTM+Attention）

### 第5步：验证效果

```bash
# CLI 快速自测
python anti_fraud_text.py "需要提前缴纳培训费10000元"     # 期望：高风险
python anti_fraud_text.py "明天下午三点组会带上周报告"    # 期望：低风险/无风险

# 起服务，走完整三层融合链路
cd flask_app && python app.py
# 然后调 POST http://localhost:5000/api/detect/text 测试
```

**验收标准：**

| 指标 | 要求 |
|------|------|
| 测试集准确率 | ≥ 85% |
| 诈骗类召回率 | ≥ 90%（宁可误报不可漏报） |
| 新话术泛化 | 用 20 条训练集没出现过的诈骗话术测试，正确率 ≥ 70% |

### 常见问题

| 问题 | 处理 |
|------|------|
| 数据集下载要申请审核 | 提前申请，等审核期间先用话术合集手工攒 2000 条跑通流程 |
| `preprocess_text.py` 报列名错误 | 检查 CSV 表头必须是 `text,label`，编码 UTF-8 |
| BiLSTM 训练太慢 | 减小 `--epochs 15`，或先只交 baseline 模型 |
| 训练时内存不够 | `--batch_size 16` |
| 模型训完服务里没生效 | 重启 Flask 服务；确认文件在 `ai-service/models/` 下且文件名没改 |

---

## 三、P1：语音 / 图像检测（第2-5周做）

### 语音
- ASR：Whisper（本地 small 模型）或讯飞开放平台
- 音频特征：MFCC + 语速/能量异常检测（`librosa`）
- 产出：语音转文本后复用文本三层检测，附加音频风险特征

### 图像
- OCR：PaddleOCR 或 EasyOCR → 识别截图文字后复用文本检测
- 二维码：`pyzbar`/`opencv` 识别收款码、钓鱼码
- 产出：`anti_fraud_image.py` 完整可调

## 四、P2：多模态融合（论文中期检查前）

- 训练晚期融合模型（各模态分数加权/堆叠分类器）
- 产出：`models/fusion_model.joblib`
- 评估融合 vs 单模态的提升，写进论文

---

## 五、环境与配置注意事项

1. **DeepSeek API key 在项目根目录 `.env`**（已被 .gitignore 忽略，不进 git）——找后端负责人拿，本地创建 `.env` 后 LLM 层自动生效
2. 临时关闭 LLM 层：`.env` 里设 `LLM_ENABLED=false`
3. **模型权重不提交 git**（.gitignore 已配置），训练完放 `ai-service/models/` 即可
4. 训练数据放 `ai-service/data/`（同样不进 git）
5. 依赖见 `ai-service/requirements.txt`，缺什么装什么

---

## 六、协作要求

| 任务 | 截止 |
|------|------|
| P0 文本模型训练+验证 | 2 周内 |
| P1 语音/图像 | 再 3 周 |
| P2 融合模型 | 论文中期检查前 |

- 每完成一个任务 git push 一次，commit message 写清楚做了什么
- 数据集获取困难、环境报错，**当天在群里说**，别憋到截止日
