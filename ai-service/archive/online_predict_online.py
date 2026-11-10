# 导入必要的库
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import warnings
warnings.filterwarnings('ignore')
import sys
import io
from sklearn.metrics import roc_curve, auc
from joblib import dump


# 解决 Windows 控制台中文乱码
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 设置matplotlib中文字体（兼容更多系统）
plt.rcParams["font.family"] = ["SimHei", "Microsoft YaHei", "SimSun", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False  # 解决负号显示问题

# 修复：确保命令行参数正确获取，若未传入则默认使用随机森林
if len(sys.argv) >= 4:
    input_train_filepath = sys.argv[1]
    model_save_path = sys.argv[2]
    model_name = sys.argv[3]
else:
    # 若未通过命令行传入参数，设置默认值（方便直接运行脚本测试）
    input_train_filepath = r'C:\idea2018\soft-cup-master\soft-cup-master\python\data\creditcard.csv'
    model_save_path = r'C:\idea2018\soft-cup-master\soft-cup-master\python\rf_fraud_model.joblib'
    model_name = 'rf'  # 默认使用随机森林
    print("未传入命令行参数，使用默认配置：")
    print(f"训练数据路径: {input_train_filepath}")
    print(f"模型保存路径: {model_save_path}")
    print(f"模型类型: 随机森林 (默认)")


# 加载数据集（优先使用命令行传入的路径，若不存在则用默认路径）
try:
    df = pd.read_csv(input_train_filepath)
except FileNotFoundError:
    print(f"指定路径 {input_train_filepath} 未找到，使用默认数据集路径")
    df = pd.read_csv(r'C:\idea2018\soft-cup-master\soft-cup-master\python\data\creditcard.csv')

print('数据集形状:', df.shape)
df.head()


# 基本信息查看
print('缺失值总数:', df.isnull().sum().sum())
print('\n类别分布:')
print(df['Class'].value_counts())
print('\n欺诈交易占比:', round(df['Class'].value_counts()[1] / len(df) * 100, 3), '%')


# 分离欺诈交易和正常交易数据
fraud = df[df['Class'] == 1]
normal = df[df['Class'] == 0]

# 打印两类交易的数量
print('正常交易数量:', len(normal))
print('欺诈交易数量:', len(fraud))


# 交易金额统计分析
print('正常交易金额统计:')
print(normal['Amount'].describe())
print('\n欺诈交易金额统计:')
print(fraud['Amount'].describe())


# 数据可视化 1: 类别分布、金额分布和时间分布
plt.figure(figsize=(12, 4))

# 第一个子图：类别分布柱状图
plt.subplot(1, 3, 1)
df['Class'].value_counts().plot(kind='bar', color=['green', 'red'])
plt.title('类别分布')
plt.xlabel('类别')
plt.ylabel('数量')
plt.xticks([0, 1], ['正常', '欺诈'], rotation=0)

# 第二个子图：交易金额分布直方图
plt.subplot(1, 3, 2)
plt.hist(normal['Amount'], bins=50, alpha=0.5, label='正常', color='green')
plt.hist(fraud['Amount'], bins=50, alpha=0.5, label='欺诈', color='red')
plt.xlabel('金额')
plt.ylabel('频率')
plt.title('金额分布')
plt.legend()
plt.yscale('log')

# 第三个子图：交易时间分布直方图
plt.subplot(1, 3, 3)
plt.hist(normal['Time'], bins=50, alpha=0.5, label='正常', color='green')
plt.hist(fraud['Time'], bins=50, alpha=0.5, label='欺诈', color='red')
plt.xlabel('时间')
plt.ylabel('频率')
plt.title('时间分布')
plt.legend()

plt.tight_layout()
plt.show()


# 计算各特征与欺诈的相关性
correlations = df.corr()['Class'].sort_values(ascending=False)
print('与欺诈最相关的前10个特征:')
print(correlations[1:11])


# 数据可视化 2: 相关性条形图
plt.figure(figsize=(10, 6))
correlations[1:16].plot(kind='barh')
plt.title('特征与欺诈的相关性')
plt.xlabel('相关系数')
plt.tight_layout()
plt.show()


# 最相关特征的分布对比
top_features = correlations[1:5].index.tolist()

# 创建2x2的子图布局
fig, axes = plt.subplots(2, 2, figsize=(12, 8))
axes = axes.flatten()

# 为每个特征绘制分布直方图
for idx, feature in enumerate(top_features):
    axes[idx].hist(normal[feature], bins=30, alpha=0.5, label='正常', color='green', density=True)
    axes[idx].hist(fraud[feature], bins=30, alpha=0.5, label='欺诈', color='red', density=True)
    axes[idx].set_title(f'{feature} 分布')
    axes[idx].set_xlabel(feature)
    axes[idx].set_ylabel('密度')
    axes[idx].legend()

plt.tight_layout()
plt.show()


def train_evaluate_fraud_model(df, fraud, normal):
    """训练和评估随机森林欺诈检测模型"""
    # 导入依赖库
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import classification_report, confusion_matrix
    import matplotlib.pyplot as plt
    import seaborn as sns
    from sklearn.metrics import roc_curve, auc
    from sklearn.ensemble import RandomForestClassifier

    model_title = '随机森林'

    # 初始化随机森林模型
    model = RandomForestClassifier(
        n_estimators=100,
        class_weight='balanced',
        random_state=42,
        n_jobs=-1
    )

    # 1. 数据预处理
    X = df.drop('Class', axis=1)
    y = df['Class']

    # 分层拆分训练集/测试集
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # 特征标准化
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # 打印数据集尺寸
    print(f'\n{model_title} 数据集拆分结果:')
    print(f'训练集大小: {X_train.shape}')
    print(f'测试集大小: {X_test.shape}')
    print('-' * 60)

    # 2. 模型训练
    print(f'正在训练{model_title}模型...')
    model.fit(X_train_scaled, y_train)

    # 3. 模型预测与评估
    y_pred = model.predict(X_test_scaled)
    y_pred_proba = model.predict_proba(X_test_scaled)[:, 1]

    # 打印分类报告
    print(f'{model_title} 分类报告:')
    print(classification_report(y_test, y_pred, target_names=['正常', '欺诈']))
    print('-' * 60)

    # 混淆矩阵可视化
    cm = confusion_matrix(y_test, y_pred)
    plt.figure(figsize=(6, 5))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues')
    plt.title(f'混淆矩阵 - {model_title}')
    plt.xlabel('预测类别')
    plt.ylabel('实际类别')
    plt.show()

    # 打印混淆矩阵详细含义
    print(f'{model_title} 混淆矩阵详情:')
    print(f'真负例 (TN): {cm[0,0]} → 实际正常，预测正常')
    print(f'假正例 (FP): {cm[0,1]} → 实际正常，预测欺诈')
    print(f'假负例 (FN): {cm[1,0]} → 实际欺诈，预测正常')
    print(f'真正例 (TP): {cm[1,1]} → 实际欺诈，预测欺诈')
    print('-' * 60)

    # 绘制ROC曲线
    fpr, tpr, thresholds = roc_curve(y_test, y_pred_proba)
    roc_auc = auc(fpr, tpr)

    plt.figure(figsize=(8, 6))
    plt.plot(fpr, tpr, color='darkorange', lw=2, label=f'ROC曲线 (面积 = {roc_auc:.2f})')
    plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel('假正例率')
    plt.ylabel('真正例率')
    plt.title(f'ROC曲线 - {model_title}')
    plt.legend(loc="lower right")
    plt.show()

    # 4. 数据集汇总统计
    print(f'{model_title} 数据集汇总:')
    print(f'总交易数: {len(df):,}')
    print(f'欺诈交易数: {len(fraud):,} ({len(fraud)/len(df)*100:.3f}%)')
    print(f'正常交易数: {len(normal):,} ({len(normal)/len(df)*100:.3f}%)')

    return model, scaler

# 只支持随机森林模型，直接调用训练函数（已通过默认值确保model_name为rf）
model, scaler = train_evaluate_fraud_model(df, fraud, normal)
if model is not None:
    dump(model, model_save_path)
    dump(scaler, f"{model_save_path}_scaler.joblib")
    print(f"\n模型 '随机森林' 和标准化器保存成功!")
    print(f"模型保存路径: {model_save_path}")
    print(f"标准化器保存路径: {model_save_path}_scaler.joblib")