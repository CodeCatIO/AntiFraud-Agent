import warnings
import pandas as pd
import random
import seaborn as sns
from matplotlib import pyplot as plt
from tensorflow.keras.models import load_model
import json
import pymysql #导入模块

#分析数据
def data_analysis(data,y):

    # 设置绘图风格
    sns.set(style="darkgrid")   
    # 绘制类别分布图
    plt.rcParams['axes.unicode_minus'] = False
    plt.rcParams['font.family'] = ['SimHei']
    ax = sns.countplot(x=y)
    ax.set_title('故障分布')
    plt.xlabel('类别')
    plt.ylabel('个数')
    plt.show()
    # 获取数据集中的所有特征列
    warnings.filterwarnings('ignore')
    data = data.drop(y.name, axis=1)
    features = data.columns
    plot_features = random.sample(list(features), k=1)
    # 遍历每个特征
    for feature in plot_features:
        data = data.reset_index(drop=True)
        # 绘制概率密度图
        sns.kdeplot(data[feature], fill=True)
        plt.title(f'{feature} 概率密度函数')
        plt.xlabel(feature)
        plt.ylabel('概率密度')
        plt.show()
    data = pd.concat([data, y], axis=1)

'''
    # 计算相关系数矩阵
    corr = data.corr()
    # 绘制热力图
    plt.figure(figsize=(80,80))
    sns.heatmap(corr, cmap='coolwarm', annot=True)
    plt.show()
'''


# conn = pymysql.connect(host='127.0.0.1',
#                        user='root',
#                        password='adou',
#                        database='softwarecup',
#                        charset='utf8')
# print("数据库连接成功")
# cursor = conn.cursor()

#预测函数
def predict(model_path, X, output_path,predict_file_path):
    
    # 加载模型
    model = load_model(model_path)
    
    # 进行预测
    y_pred = model.predict(X)
    y_pred = y_pred.argmax(axis=1)
    # 将预测结果转换为字典
    result = {}
    for i, pred in enumerate(y_pred):
        result[str(i)] = int(pred)
    # 将结果写入 JSON 文件
    with open(output_path, 'w') as f:
        json.dump(result, f)

    return 