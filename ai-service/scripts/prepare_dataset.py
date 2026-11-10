#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
任务1：Telecom_Fraud_Texts_5 数据集准备脚本

输入：data/raw/Telecom_Fraud_Texts_5-main/label0{0..4}-last.csv
  - CSV 两列，表头 content,label
  - label00 正常(原始label=0)，label01~04 诈骗(原始label为中文类别名)
  - 编码不一致：label04 为 GBK，其余为 UTF-8（按 utf-8-sig -> gbk 顺序尝试）

处理：
  1. 读取 5 个 CSV（编码自动兼容），content -> 文本，原始 label 存为 category
  2. 二分类标签：category 为 "0" 的记 0（正常），其余记 1（诈骗）
  3. 清洗：去除空/纯空白文本、按 content 去重、超过 500 字的文本截断到 500 字
     （选择截断而非丢弃：超长样本仅极少数，截断保留其前段诈骗话术信息）
  4. 按 label 分层抽样切分 train/val/test = 8:1:1（random_state=42）

输出：data/text/processed/{train,val,test}.csv，表头 content,label,category
"""
import os
import pandas as pd
from sklearn.model_selection import train_test_split

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AI_SERVICE_DIR = os.path.dirname(SCRIPT_DIR)
RAW_DIR = os.path.join(AI_SERVICE_DIR, 'data', 'raw', 'Telecom_Fraud_Texts_5-main')
PROCESSED_DIR = os.path.join(AI_SERVICE_DIR, 'data', 'text', 'processed')

MAX_CHARS = 500
RANDOM_STATE = 42

FILES = [f'label0{i}-last.csv' for i in range(5)]
ENCODINGS = ('utf-8-sig', 'gbk')  # 按任务书要求的顺序尝试


def read_csv_auto(path):
    """按 utf-8-sig -> gbk 顺序尝试读取，返回 (DataFrame, 实际编码)"""
    last_err = None
    for enc in ENCODINGS:
        try:
            return pd.read_csv(path, encoding=enc, dtype={'content': str, 'label': str}), enc
        except UnicodeDecodeError as e:
            last_err = e
    raise UnicodeDecodeError(
        'auto', b'', 0, 1, f'{path} 用 {ENCODINGS} 均无法解码: {last_err}')


def load_all():
    frames = []
    print('[读取] 5 个 CSV（编码 utf-8-sig -> gbk 自动兼容）')
    for fname in FILES:
        path = os.path.join(RAW_DIR, fname)
        df, enc = read_csv_auto(path)
        df['category'] = df['label'].astype(str).str.strip()
        df['bin_label'] = (df['category'] != '0').astype(int)
        print(f'  {fname}: {len(df)} 条, 编码={enc}, '
              f"类别='{df['category'].iloc[0]}' -> label={df['bin_label'].iloc[0]}")
        frames.append(df[['content', 'bin_label', 'category']])
    data = pd.concat(frames, ignore_index=True)
    data = data.rename(columns={'bin_label': 'label'})
    print(f'  合计读取: {len(data)} 条')
    return data


def clean(df):
    print('\n[清洗]')
    n0 = len(df)
    df['content'] = df['content'].fillna('').astype(str).str.strip()
    df = df[df['content'].str.len() > 0]
    n1 = len(df)
    print(f'  去除空/纯空白: {n0} -> {n1}（-{n0 - n1}）')

    n0 = len(df)
    df = df.drop_duplicates(subset=['content'], keep='first').reset_index(drop=True)
    print(f'  按 content 去重: {n0} -> {len(df)}（-{n0 - len(df)}）')

    over = (df['content'].str.len() > MAX_CHARS).sum()
    df['content'] = df['content'].str.slice(0, MAX_CHARS)
    print(f'  超长文本(>{MAX_CHARS}字): {over} 条，统一截断到前 {MAX_CHARS} 字（保留不丢弃）')
    return df


def split(df):
    print('\n[切分] 按 label 分层 8:1:1（random_state=42）')
    train_df, temp_df = train_test_split(
        df, test_size=0.2, random_state=RANDOM_STATE, stratify=df['label'])
    val_df, test_df = train_test_split(
        temp_df, test_size=0.5, random_state=RANDOM_STATE, stratify=temp_df['label'])
    return (train_df.reset_index(drop=True),
            val_df.reset_index(drop=True),
            test_df.reset_index(drop=True))


def report_split(name, df):
    n = len(df)
    n1 = int(df['label'].sum())
    n0 = n - n1
    ratio = f'{n0 / n:.2%} : {n1 / n:.2%}'
    print(f'  {name}: {n} 条 | 正常0={n0} 诈骗1={n1} | 负正比例 {ratio}')
    cats = df['category'].value_counts()
    for cat, cnt in cats.items():
        print(f'      {cat}: {cnt}')
    return n, n0, n1


def main():
    print('=' * 60)
    print('Telecom_Fraud_Texts_5 数据准备')
    print('=' * 60)
    if not os.path.isdir(RAW_DIR):
        raise FileNotFoundError(f'数据集目录不存在: {RAW_DIR}')

    data = load_all()
    data = clean(data)

    print('\n[清洗后总览]')
    print(f"  总量: {len(data)} 条 | 正常(0)={int((data['label'] == 0).sum())} "
          f"诈骗(1)={int((data['label'] == 1).sum())}")
    print('  原始类别分布:')
    for cat, cnt in data['category'].value_counts().items():
        print(f'    {cat}: {cnt}')

    train_df, val_df, test_df = split(data)

    os.makedirs(PROCESSED_DIR, exist_ok=True)
    summary = {}
    for name, part in [('train', train_df), ('val', val_df), ('test', test_df)]:
        part.to_csv(os.path.join(PROCESSED_DIR, f'{name}.csv'),
                    index=False, encoding='utf-8',
                    columns=['content', 'label', 'category'])
        print()
        summary[name] = report_split(name, part)

    print(f'\n[输出] -> {PROCESSED_DIR}\\{{train,val,test}}.csv')
    print(f'  表头: content,label,category')


if __name__ == '__main__':
    main()
