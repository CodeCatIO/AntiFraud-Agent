# 图像诈骗检测传统机器学习 baseline 实验报告

## 数据规模

- 总样本数（含增强）: 3896 张
- 真（正常）: 1740 张
- 伪（诈骗截图/篡改）: 2156 张

## 特征说明

| 特征组 | 维度 | 说明 |
|--------|------|------|
| ela | 8 | ELA 误差图统计（均值/方差/分位数/偏度等）|
| basic | 19 | RGB/HSV 统计 + 亮度对比度 + 拉普拉斯+ 边缘密度 + 噪声残差 |
| ela_basic | 27 | ELA + 基础特征 |
| full | 31 | ELA + 基础 + GLCM 纹理特征 |

## Ablation Study 实验结果

| 特征 | 模型 | Holdout Acc | Holdout P | Holdout R | Holdout F1 | CV-F1 | 状态 |
|------|------|-------------|-----------|-----------|------------|-------|------|
| ela | svm | 0.5788 | 0.6259 | 0.5788 | 0.5687 | 0.5765 | ✅ |
| ela | random_forest | 0.6781 | 0.6784 | 0.6781 | 0.6782 | 0.6933 | ✅ |
| ela | logistic_regression | 0.5634 | 0.5878 | 0.5634 | 0.5615 | 0.5599 | ✅ |
| basic | svm | 0.7774 | 0.7769 | 0.7774 | 0.7771 | 0.7615 | ✅ |
| basic | random_forest | 0.9606 | 0.9606 | 0.9606 | 0.9606 | 0.9607 | ✅ ⭐ |
| basic | logistic_regression | 0.6858 | 0.6929 | 0.6858 | 0.6871 | 0.6843 | ✅ |
| ela_basic | svm | 0.7808 | 0.7809 | 0.7808 | 0.7809 | 0.763 | ✅ |
| ela_basic | random_forest | 0.9375 | 0.9375 | 0.9375 | 0.9375 | 0.9342 | ✅ |
| ela_basic | logistic_regression | 0.7106 | 0.7146 | 0.7106 | 0.7116 | 0.6923 | ✅ |
| full | svm | 0.786 | 0.7868 | 0.786 | 0.7863 | 0.7735 | ✅ |
| full | random_forest | 0.9264 | 0.9266 | 0.9264 | 0.9264 | 0.928 | ✅ |
| full | logistic_regression | 0.7098 | 0.7123 | 0.7098 | 0.7106 | 0.7087 | ✅ |

## 可视化产出

- ELA 误差图对比: `ela_visualization.png`
- 样本示例拼图: `sample_montage.png`
- 混淆矩阵: `confusion_matrix_*.png`

## 最佳模型

- 组合: **basic__random_forest**
- 得分: 0.9607
- 已保存到: `models/image_baseline.joblib`

> 该模型已接入 `anti_fraud_image.py`，启动 Flask 服务后 `/api/detect/image` 会自动使用 ML 预测。

> 注：类激活图（CAM）可视化属于深度学习（ResNet/EfficientNet）阶段，不在 baseline 范围。
