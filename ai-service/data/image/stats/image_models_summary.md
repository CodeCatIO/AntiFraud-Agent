# 图像真伪检测三模型对比报告（CIFAKE 数据集）

## 数据集

- 名称：CIFAKE（dragonintelligence/CIFAKE-image-dataset，HuggingFace 镜像 hf-mirror.com 下载）
- 论文：CIFAKE: Image Classification and Explainable Identification of AI-Generated Synthetic Images, IEEE 2024
- 训练抽样：8000 张（真/伪各 4000）
- 测试抽样：2000 张（真/伪各 1000）
- 标签：真=CIFAR-10 真实照片；伪=Stable Diffusion 生成图（32x32）
- 特征：ELA 误差统计(8) + 颜色/噪声/边缘(19) + GLCM 纹理(4) = 31 维

## 测试集指标

| 模型 | Accuracy | Precision | Recall | F1 | 伪类 Recall |
|------|----------|-----------|--------|----|-------------|
| 逻辑回归 LogisticRegression | 0.8655 | 0.8657 | 0.8655 | 0.8655 | 0.853 |
| 随机森林 RandomForest | 0.877 | 0.877 | 0.877 | 0.877 | 0.873 |
| 支持向量机 RBF-SVM ⭐默认 | 0.913 | 0.913 | 0.913 | 0.913 | 0.908 |

> 三个模型文件分别为 `models/image_lr.joblib`、`image_rf.joblib`、`image_svm.joblib`，可在检测页面下拉选择；`image_baseline.joblib` 指向最佳模型。
