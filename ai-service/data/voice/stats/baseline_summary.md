# 语音诈骗检测传统机器学习 baseline 实验报告

## 数据规模

- 总样本数（含增强）: 11196 条
  - 特征 mean: 11196 样本, 20 维

## 特征说明

| 特征 | 维度 | 说明 |
|------|------|------|
| mean | 20 | MFCC 每维均值 |
| stats | 40 | MFCC 均值+标准差 |
| delta | 60 | MFCC 均值 + Δ均值 + ΔΔ均值 |

## Ablation Study 实验结果

| 特征 | 模型 | Holdout Acc | Holdout P | Holdout R | Holdout F1 | CV-F1 | 状态 |
|------|------|-------------|-----------|-----------|------------|-------|------|
| mean | gmm | 0.9101 | 0.9101 | 0.9101 | 0.9101 | 0.9095 | ✅ |
| mean | svm | 0.9729 | 0.9729 | 0.9729 | 0.9729 | 0.9737 | ✅ ⭐ |
| mean | random_forest | 0.9699 | 0.9699 | 0.9699 | 0.9699 | 0.9712 | ✅ |

## 可视化产出

- MFCC 热力图对比: `mfcc_visualization.png`
- 频谱图对比: `spectrogram.png`
- 混淆矩阵: `confusion_matrix_*.png`

## 最佳模型

- 组合: **mean__svm**
- 得分: 0.9737
- 已保存到: `models/voice_baseline.joblib`

> 该模型已接入 `anti_fraud_voice.py`，启动 Flask 服务后 `/api/detect/voice` 会自动使用 ML 预测。
