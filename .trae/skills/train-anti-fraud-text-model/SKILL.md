---
name: train-anti-fraud-text-model
description: Train Chinese anti-fraud text models (TF-IDF+LinearSVC, BiLSTM) on Telecom_Fraud_Texts_5 and wire into ai-service. Use for 训练反诈文本模型, retraining text_baseline.joblib or text_bilstm.pt, 重新训练本地模型, or 生成 text_model_report. Not for voice or image models.
---

# 训练反诈文本本地模型（TF-IDF+LinearSVC / BiLSTM）

把 Telecom_Fraud_Texts_5 语料训练成可被 `anti_fraud_text.py` 三层融合自动加载的二分类模型。
本技能只规定**编排顺序、输入输出契约与项目特定坑点**；不要重写训练脚本，不要改三层融合逻辑和模型文件名。

## 固定契约（违反即失败）

- 原始数据：`ai-service/data/raw/Telecom_Fraud_Texts_5-main/label0{0..4}-last.csv` + GPLv3 `LICENSE`（必须保留）
- 切分后数据：`ai-service/data/text/processed/{train,val,test}.csv`，表头固定为 **`content,label,category`**
  （label 0=正常 1=诈骗；category 存原始中文类别，"0" 表示正常）
- 模型产物名写死：`models/text_baseline.joblib`、`models/text_bilstm.pt`(+`_vocab.json`/`_meta.json`)
- 报告产物：`reports/text_model_report.md`、`reports/confusion_matrix_baseline.png`、`reports/confusion_matrix_bilstm.png`
- 切分 **8:1:1**，按 label 分层，`random_state=42`
- 验收硬指标：test accuracy ≥ 85%，**诈骗类 recall ≥ 90%（宁可误报不可漏报）**

## 环境（Windows 11 + Python 3.14，纯 CPU）

`pandas scikit-learn numpy jieba joblib matplotlib`；BiLSTM 另需 CPU 版 torch：
`python -m pip install torch --index-url https://download.pytorch.org/whl/cpu`
参考版本：sklearn 1.9.1 / pandas 3.0.6 / torch 2.14.1+cpu；CPU Ryzen 7 5800H。

## 流水线（在 ai-service 目录下严格按序执行，每步检查输出再继续）

1. 准备数据：`python scripts/prepare_dataset.py`
   读 5 个 CSV（utf-8-sig→gbk 自动回退）→ 去空/去重/超 500 字截断 → 8:1:1 分层切分。
   实测：读取 11773（label00=7773，其余各 1000）→ 去重后 11570（正常 7573/诈骗 3997）→ 9256/1157/1157。
2. baseline：`python scripts/train_text_baseline.py`
   4 特征×3 模型共 12 组 ablation，按 5 折 CV-F1 选最佳。实测最佳 word_char_combined+linear_svc，
   test acc=100%、诈骗 recall=100%，含 12 组 CV 约 255 秒。自动落 joblib、reports 指标 JSON 与混淆矩阵。
3. BiLSTM：`python scripts/train_text_bilstm.py`（默认 epochs=30/batch=32，patience=5 早停）
   CPU 实测 8 epoch 早停、336.8 秒，远低于 2 小时，**无需降 epochs/batch**。
   test acc=99.74%、诈骗 recall=100%（3 条正常误报）。超 2 小时才用 `--epochs 15` 并在报告说明。
4. 写报告：汇总到 `reports/text_model_report.md`（数据说明/逐类 P/R/F1/两张混淆矩阵/
   超参/耗时/环境/主模型结论/端到端 JSON/模型文件大小）。
5. 端到端：后台 `python flask_app\app.py`，先 `GET /api/health`（text=true），
   再 `POST /api/detect/text`（body `{"content":"..."}`）验 4 条：培训费入职、养老院收集身份信息
   → 高风险；组会通知、快递取件码 → 低风险。把完整返回 JSON 原样写入报告。

## 已确认的坑（真实踩过，不要重复）

- **label04-last.csv 是 GBK**，label00-03 是 utf-8-sig；读取必须按 `utf-8-sig → gbk` 顺序 try。
- label04 文件内原始类别实测是"**冒充领导、熟人类**"（README 同此），与"杀猪盘"说法不符，以文件实际值存 category。
- 任务书给的 7838/11838 是约数；pandas 按 CSV 引号规则实际解析 7773/11773，报告中如实说明。
- 只许改训练脚本去适配数据格式，**不许把数据输出改成 text/tokens 去迁就脚本**：
  baseline 脚本内部 jieba 生成 tokens；`deep_text_common.load_processed_data` 用 `r.get('content') or r.get('text')` 兼容。
- matplotlib 混淆矩阵中文乱码：在两脚本 import pyplot 后注册
  `C:\Windows\Fonts\msyh.ttc`（回退 simhei/simsun）并设 `font.sans-serif`、`axes.unicode_minus=False`。
- PowerShell：多行临时代码用 `@' ... '@ | python -`（不要用 bash heredoc）；
  中文 JSON body 用 `[System.Text.Encoding]::UTF8.GetBytes($body)`。
- LLM 层无 `DEEPSEEK_API_KEY` 自动跳过，不影响本地验证。同源切分指标接近满分，报告须提示泛化性风险。

## Git 规则（本仓库是解压包，默认无 .git）

- 首次需 `git init -b master` 并本地配 user.name/email；**只提交不 push**，不配 remote。
- `.gitignore` 忽略 `*.joblib *.pt *.pth *.pkl`；`**/data/*.csv` 只匹配 data 直接下层，
  嵌套目录（raw/Telecom.../、text/processed/）实际不被命中——不要以为它会生效。
- 5 个原始 CSV 用 `git add -f` 显式添加；`data/text/processed`、`data/text/stats` 是中间产物，
  用 `git rm --cached -r` 撤出首次提交（未出生分支上 `restore --staged` 会报 could not resolve HEAD）。
- 提交前用 `git diff --cached --name-only` 核对：无 .pt/.joblib、无 processed/stats；
  `git ls-files | findstr ".pt .joblib"` 提交后再验一次。
- 权重只把字节数写进报告（实测 joblib 535,710B / pt 4,409,297B），**停下等人类决定 Gitee LFS 还是发行版附件**，
  禁止 filter-branch、禁止 force push。
- commit message 中文，形如：`feat(ai): 新增数据集准备脚本并完成文本模型训练(baseline acc=100%, bilstm acc=99.74%)`

## 红线

- 不改 `anti_fraud_text.py` 融合逻辑与加载文件名；重训后必须重启 Flask 才加载新权重。
- 不删 `data/raw/.../LICENSE`；不手改原始 CSV；不编造指标，达不到硬指标就分析原因并调参重跑。
