# 语音深伪检测三模型对比报告（Deepfake Audio Detection v4）

## 数据集

- 名称：Deepfake Audio Detection Dataset v4（garystafford/deepfake-audio-detection，HuggingFace 镜像 hf-mirror.com 下载，CC-BY-4.0）
- 总样本：1866 条（真人 real 933 / AI 合成 fake 933），2.5~13 秒，16kHz FLAC
- 真人：YouTube 真人语音；合成：6 个 TTS/语音克隆平台生成
- 分层切分：训练 1492 / 测试 374（8:2）
- 特征：MFCC 均值 + Δ 均值 + ΔΔ 均值 = 60 维（n_mfcc=20）

## 测试集指标

| 模型 | Accuracy | Precision | Recall | F1 | 伪类 Recall |
|------|----------|-----------|--------|----|-------------|
| 高斯混合模型 GMM ⭐默认 | 0.9652 | 0.9654 | 0.9652 | 0.9652 | 0.9733 |
| 支持向量机 RBF-SVM | 0.9652 | 0.9654 | 0.9652 | 0.9652 | 0.9572 |
| 随机森林 RandomForest | 0.9358 | 0.9363 | 0.9358 | 0.9358 | 0.9519 |

> 三个模型文件分别为 `models/voice_gmm.joblib`、`voice_svm.joblib`、`voice_rf.joblib`，可在检测页面下拉选择；`voice_baseline.joblib` 指向最佳模型。
