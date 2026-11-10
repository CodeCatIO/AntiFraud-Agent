#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文本数据预处理脚本

处理流程：去重 -> 去噪 -> jieba分词 -> 长度统计 -> 8:1:1划分

输入：data/text/raw/ 下的 CSV（列：text, label）
  - text: 短信内容
  - label: 1=诈骗, 0=正常

输出：data/text/processed/{train,val,test}.csv + data/text/stats/stats.json

数据集来源（需用户自行下载放入 raw/ 目录）：
  - 天池 80w 垃圾短信：https://tianchi.aliyun.com/dataset
  - Kaggle SMS Spam Collection：https://www.kaggle.com/uciml/sms-spam-collection-dataset
  - GitHub 诈骗话术模板：开源诈骗短信标注集
"""
import os
import re
import json
import pandas as pd
import jieba
from collections import Counter
from sklearn.model_selection import train_test_split

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AI_SERVICE_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(AI_SERVICE_DIR, 'data')
RAW_DIR = os.path.join(DATA_DIR, 'text', 'raw')
PROCESSED_DIR = os.path.join(DATA_DIR, 'text', 'processed')
STATS_DIR = os.path.join(DATA_DIR, 'text', 'stats')

# 正则模式
URL_PATTERN = re.compile(r'https?://\S+|www\.\S+')
PHONE_PATTERN = re.compile(r'1[3-9]\d{9}')
SPECIAL_CHAR_PATTERN = re.compile(r'[^\u4e00-\u9fa5a-zA-Z0-9\s<>]')


def load_raw_data():
    """加载 raw 目录下所有 CSV"""
    csv_files = [f for f in os.listdir(RAW_DIR) if f.endswith('.csv')]
    if not csv_files:
        raise FileNotFoundError(
            f"未找到CSV文件，请先在 {RAW_DIR} 放入数据或运行 create_sample_data.py"
        )

    dfs = []
    for f in csv_files:
        path = os.path.join(RAW_DIR, f)
        df = pd.read_csv(path, encoding='utf-8')
        dfs.append(df)
        print(f"  读取 {f}: {len(df)} 条")

    df = pd.concat(dfs, ignore_index=True)
    print(f"  合计 {len(df)} 条")
    return df


def remove_duplicates(df):
    """去重"""
    before = len(df)
    df = df.drop_duplicates(subset=['text']).reset_index(drop=True)
    after = len(df)
    print(f"  去重: {before} -> {after}（删除 {before - after} 条）")
    return df


def denoise_text(text):
    """去噪：清理URL、特殊字符、多余空白"""
    if not isinstance(text, str):
        return ""
    # URL 替换为占位符
    text = URL_PATTERN.sub('<URL>', text)
    # 电话号码替换为占位符
    text = PHONE_PATTERN.sub('<PHONE>', text)
    # 特殊字符清理（保留中文/英文/数字/空白/占位符）
    text = SPECIAL_CHAR_PATTERN.sub(' ', text)
    # 多余空白
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def tokenize(text):
    """jieba分词"""
    tokens = jieba.lcut(text)
    return ' '.join(tokens)


def compute_stats(df):
    """计算统计信息"""
    stats = {
        'total_samples': len(df),
        'fraud_samples': int(df['label'].sum()),
        'normal_samples': int((df['label'] == 0).sum()),
        'fraud_ratio': round(float(df['label'].mean()), 4),
        'avg_char_length': round(float(df['text'].str.len().mean()), 2),
        'max_char_length': int(df['text'].str.len().max()),
        'min_char_length': int(df['text'].str.len().min()),
        'avg_token_length': round(float(df['tokens'].str.split().str.len().mean()), 2),
    }

    # 词频 Top10（诈骗样本）
    fraud_tokens = []
    for tokens_str in df[df['label'] == 1]['tokens']:
        fraud_tokens.extend(tokens_str.split())
    stats['top10_fraud_words'] = Counter(fraud_tokens).most_common(10)

    # 示例样本
    stats['examples'] = {
        'fraud': df[df['label'] == 1]['text'].head(3).tolist(),
        'normal': df[df['label'] == 0]['text'].head(3).tolist(),
    }
    return stats


def main():
    print("=" * 60)
    print("文本数据预处理")
    print("=" * 60)

    # 1. 加载数据
    print("\n[1/5] 加载原始数据...")
    df = load_raw_data()

    # 2. 去重
    print("\n[2/5] 去重...")
    df = remove_duplicates(df)

    # 3. 去噪
    print("\n[3/5] 去噪...")
    df['text'] = df['text'].apply(denoise_text)
    df = df[df['text'].str.len() > 0].reset_index(drop=True)  # 去除空文本
    print(f"  去噪后剩余 {len(df)} 条")

    # 4. 分词
    print("\n[4/5] jieba分词...")
    df['tokens'] = df['text'].apply(tokenize)

    # 5. 划分数据集 8:1:1（任务书 P0 要求）
    print("\n[5/5] 划分数据集 (8:1:1)...")
    # 小数据集时分层抽样可能失败，动态判断
    use_stratify = min(df['label'].value_counts()) >= 2
    train_df, temp_df = train_test_split(
        df, test_size=0.2, random_state=42,
        stratify=df['label'] if use_stratify else None
    )
    temp_use_stratify = use_stratify and min(temp_df['label'].value_counts()) >= 2
    val_df, test_df = train_test_split(
        temp_df, test_size=0.5, random_state=42,
        stratify=temp_df['label'] if temp_use_stratify else None
    )
    print(f"  训练集: {len(train_df)} | 验证集: {len(val_df)} | 测试集: {len(test_df)}")

    # 保存
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    train_df.to_csv(os.path.join(PROCESSED_DIR, 'train.csv'), index=False, encoding='utf-8')
    val_df.to_csv(os.path.join(PROCESSED_DIR, 'val.csv'), index=False, encoding='utf-8')
    test_df.to_csv(os.path.join(PROCESSED_DIR, 'test.csv'), index=False, encoding='utf-8')
    print(f"\n  保存 -> {PROCESSED_DIR}/{{train,val,test}}.csv")

    # 统计
    os.makedirs(STATS_DIR, exist_ok=True)
    stats = compute_stats(df)
    stats['split'] = {'train': len(train_df), 'val': len(val_df), 'test': len(test_df)}
    with open(os.path.join(STATS_DIR, 'stats.json'), 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"  统计 -> {STATS_DIR}/stats.json")
    print(f"\n文本预处理完成。")


if __name__ == '__main__':
    main()
