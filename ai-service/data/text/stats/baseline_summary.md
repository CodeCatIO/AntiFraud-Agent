# 文本检测传统机器学习 baseline 实验报告

## 数据规模

- 训练集(train+val): 4131 条
- 测试集: 460 条
- 总计: 4591 条

## Ablation Study 实验结果

| 特征 | 模型 | Holdout Acc | Holdout P | Holdout R | Holdout F1 | CV-F1 | 状态 |
|------|------|-------------|-----------|-----------|------------|-------|------|
| word_1gram | multinomial_nb | 0.9978 | 0.9978 | 0.9978 | 0.9978 | 0.9926 | ✅ |
| word_1gram | linear_svc | 1.0 | 1.0 | 1.0 | 1.0 | 0.997 | ✅ |
| word_1gram | random_forest | 0.9957 | 0.9957 | 0.9957 | 0.9957 | 0.9902 | ✅ |
| word_12gram | multinomial_nb | 0.9978 | 0.9978 | 0.9978 | 0.9978 | 0.9926 | ✅ |
| word_12gram | linear_svc | 1.0 | 1.0 | 1.0 | 1.0 | 0.9972 | ✅ ⭐ |
| word_12gram | random_forest | 0.9913 | 0.9915 | 0.9913 | 0.9913 | 0.9878 | ✅ |
| char_234gram | multinomial_nb | 0.9957 | 0.9957 | 0.9957 | 0.9957 | 0.9922 | ✅ |
| char_234gram | linear_svc | 1.0 | 1.0 | 1.0 | 1.0 | 0.9967 | ✅ |
| char_234gram | random_forest | 0.9957 | 0.9957 | 0.9957 | 0.9957 | 0.9915 | ✅ |
| word_char_combined | multinomial_nb | 0.9978 | 0.9978 | 0.9978 | 0.9978 | 0.9928 | ✅ |
| word_char_combined | linear_svc | 1.0 | 1.0 | 1.0 | 1.0 | 0.9967 | ✅ |
| word_char_combined | random_forest | 0.9957 | 0.9957 | 0.9957 | 0.9957 | 0.9917 | ✅ |

## 最佳模型

- 组合: **word_12gram__linear_svc**
- 得分: 0.9972
- 已保存到: `models/text_baseline.joblib`

> 该模型已接入 `anti_fraud_text.py`，启动 Flask 服务后 `/api/detect/text` 会自动使用 ML 预测。
