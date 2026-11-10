#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
语音深伪检测三模型训练脚本（Deepfake Audio Detection Dataset v4）

数据集（网上下载，HuggingFace 镜像）:
  garystafford/deepfake-audio-detection (CC-BY-4.0)
  - 1866 条 2.5~13 秒语音（933 真人 real / 933 AI 合成 fake）
  - real: YouTube 真人语音片段；fake: 6 个 TTS/语音克隆平台合成
  - FLAC 16kHz 单声道，parquet 两个分片
  - 标签: 0=real -> 项目 0(正常); 1=fake -> 1(诈骗/AI伪造)

输入:
  data/raw/voice_df/train-0000{0,1}-of-00002.parquet
输出:
  - models/voice_gmm.joblib / voice_svm.joblib / voice_rf.joblib
    bundle: {pipeline, feature_kind, n_mfcc, target_sr, model_name, metrics, dataset}
  - models/voice_baseline.joblib         三模型中测试集 F1 最高者（兼容默认推理路径）
  - data/voice/processed/voice_deepfake_features.npz（特征缓存）
  - data/voice/stats/voice_models_results.json
  - data/voice/stats/confusion_matrix_voice_<model>.png
  - data/voice/stats/voice_models_summary.md

三个模型（特征统一: MFCC 均值 + Δ 均值 + ΔΔ 均值 = 60 维, n_mfcc=20, 16kHz）:
  1. gmm  每类一个高斯混合模型，按对数似然判类
  2. svm  RBF 核支持向量机
  3. rf   随机森林

用法:
  python train_voice_models.py
"""
import os
import io
import sys
import json
import warnings

import numpy as np
import librosa
import soundfile as sf
import pyarrow.parquet as pq
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
)
import joblib

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AI_SERVICE_DIR = os.path.dirname(SCRIPT_DIR)
# 保证 from gmm_classifier import GMMClassifier 可用（类需在稳定模块下，
# 否则 joblib 会把它 pickle 成 __main__.GMMClassifier，推理端无法反序列化）
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
from gmm_classifier import GMMClassifier  # noqa: E402

RAW_DIR = os.path.join(AI_SERVICE_DIR, 'data', 'raw', 'voice_df')
PROCESSED_DIR = os.path.join(AI_SERVICE_DIR, 'data', 'voice', 'processed')
STATS_DIR = os.path.join(AI_SERVICE_DIR, 'data', 'voice', 'stats')
MODELS_DIR = os.path.join(AI_SERVICE_DIR, 'models')

TARGET_SR = 16000
N_MFCC = 20
RANDOM_STATE = 42
TEST_SIZE = 0.2


# ============================================================
# 特征提取
# ============================================================

def extract_delta_mfcc(flac_bytes, n_mfcc=N_MFCC, target_sr=TARGET_SR):
    """FLAC 字节 -> 16k 单声道 -> MFCC 均值 + Δ均值 + ΔΔ均值 (60,)"""
    y, sr = sf.read(io.BytesIO(flac_bytes), dtype='float32')
    if y.ndim > 1:
        y = np.mean(y, axis=1)
    if sr != target_sr:
        y = librosa.resample(y, orig_sr=sr, target_sr=target_sr)
    mfcc = librosa.feature.mfcc(y=y, sr=target_sr, n_mfcc=n_mfcc)
    d1 = librosa.feature.delta(mfcc)
    d2 = librosa.feature.delta(mfcc, order=2)
    return np.concatenate([
        np.mean(mfcc, axis=1),
        np.mean(d1, axis=1),
        np.mean(d2, axis=1),
    ])


def build_features(force=False):
    """读两个 parquet 分片，全量提取 60 维 ΔMFCC 特征"""
    cache = os.path.join(PROCESSED_DIR, 'voice_deepfake_features.npz')
    if (not force) and os.path.exists(cache):
        print(f'  使用特征缓存: {cache}')
        z = np.load(cache)
        return z['X'], z['y']

    parquets = [
        os.path.join(RAW_DIR, 'train-00000-of-00002.parquet'),
        os.path.join(RAW_DIR, 'train-00001-of-00002.parquet'),
    ]
    feats, labels = [], []
    for p in parquets:
        if not os.path.exists(p):
            raise FileNotFoundError(f'缺少 {p}，请先下载语音数据集')
        pf = pq.ParquetFile(p)
        print(f'  {os.path.basename(p)}: {pf.metadata.num_rows} 行, '
              f'{pf.num_row_groups} 个 row group')
        for rg in range(pf.num_row_groups):
            tbl = pf.read_row_group(rg)
            audios = tbl.column('audio').to_pylist()
            labs = tbl.column('label').to_pylist()
            for au, lab in zip(audios, labs):
                try:
                    feats.append(extract_delta_mfcc(au['bytes']))
                    labels.append(int(lab))  # 0=real 1=fake，与项目标签一致
                except Exception as e:
                    print(f'    跳过损坏音频: {e}')

    X = np.array(feats, dtype=np.float64)
    y = np.array(labels, dtype=np.int64)
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    np.savez_compressed(cache, X=X, y=y)
    print(f'  特征缓存 -> {cache}')
    return X, y


# ============================================================
# 模型
# ============================================================

def build_model(name):
    if name == 'gmm':
        return Pipeline([
            ('scaler', StandardScaler()),
            ('clf', GMMClassifier(n_components=4)),
        ])
    if name == 'svm':
        return Pipeline([
            ('scaler', StandardScaler()),
            ('clf', SVC(
                C=1.5, kernel='rbf', gamma='scale',
                probability=True, random_state=RANDOM_STATE,
                class_weight='balanced')),
        ])
    if name == 'rf':
        return Pipeline([
            ('scaler', StandardScaler()),
            ('clf', RandomForestClassifier(
                n_estimators=300, max_depth=24, min_samples_leaf=2,
                random_state=RANDOM_STATE,
                class_weight='balanced', n_jobs=-1)),
        ])
    raise ValueError(f'Unknown model: {name}')


def compute_metrics(y_true, y_pred):
    return {
        'accuracy': round(float(accuracy_score(y_true, y_pred)), 4),
        'precision': round(float(precision_score(
            y_true, y_pred, average='weighted', zero_division=0)), 4),
        'recall': round(float(recall_score(
            y_true, y_pred, average='weighted', zero_division=0)), 4),
        'f1': round(float(f1_score(
            y_true, y_pred, average='weighted', zero_division=0)), 4),
        'recall_fake': round(float(recall_score(
            y_true, y_pred, pos_label=1, zero_division=0)), 4),
        'confusion_matrix': confusion_matrix(
            y_true, y_pred, labels=[0, 1]).tolist(),
    }


def plot_confusion_matrix(cm, title, save_path):
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'SimSun']
    plt.rcParams['axes.unicode_minus'] = False
    fig, ax = plt.subplots(figsize=(5, 4))
    im = ax.imshow(np.array(cm), interpolation='nearest', cmap=plt.cm.Blues)
    ax.set_title(title)
    fig.colorbar(im)
    classes = ['真(真人)', '伪(AI合成)']
    ax.set_xticks([0, 1]); ax.set_yticks([0, 1])
    ax.set_xticklabels(classes); ax.set_yticklabels(classes)
    ax.set_xlabel('Predicted'); ax.set_ylabel('True')
    thresh = np.max(cm) / 2 if np.max(cm) > 0 else 0.5
    for i in range(2):
        for j in range(2):
            ax.text(j, i, format(int(cm[i][j]), 'd'),
                    ha='center', va='center',
                    color='white' if cm[i][j] > thresh else 'black')
    fig.tight_layout()
    fig.savefig(save_path, dpi=120)
    plt.close(fig)


MODEL_FILES = {
    'gmm': 'voice_gmm.joblib',
    'svm': 'voice_svm.joblib',
    'rf': 'voice_rf.joblib',
}
MODEL_LABELS = {
    'gmm': '高斯混合模型 GMM',
    'svm': '支持向量机 RBF-SVM',
    'rf': '随机森林 RandomForest',
}


def main():
    warnings.filterwarnings('ignore')
    print('=' * 60)
    print('语音深伪检测三模型训练（real vs TTS/语音克隆, ΔMFCC 60维）')
    print('=' * 60)

    os.makedirs(MODELS_DIR, exist_ok=True)
    os.makedirs(STATS_DIR, exist_ok=True)

    # 1. 特征
    print('\n[1/4] 提取 ΔMFCC 特征（1866 条 FLAC）...')
    X, y = build_features()
    print(f'  X={X.shape}, 真(real)={int((y == 0).sum())} '
          f'伪(fake)={int((y == 1).sum())}')

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, stratify=y, random_state=RANDOM_STATE)
    print(f'  train={len(y_train)}  test={len(y_test)}（分层 8:2）')

    # 2. 训练三模型
    results = {}
    best_name, best_f1, best_pipeline = None, -1.0, None
    for name in ('gmm', 'svm', 'rf'):
        print(f'\n[2/4] 训练 {MODEL_LABELS[name]} ...')
        pipe = build_model(name)
        pipe.fit(X_train, y_train)
        y_pred = pipe.predict(X_test)
        m = compute_metrics(y_test, y_pred)
        results[name] = m
        print(f"  acc={m['accuracy']}  P={m['precision']}  "
              f"R={m['recall']}  F1={m['f1']}  伪类recall={m['recall_fake']}")

        bundle = {
            'pipeline': pipe,
            'feature_kind': 'delta',
            'n_mfcc': N_MFCC,
            'target_sr': TARGET_SR,
            'model_name': name,
            'model_label': MODEL_LABELS[name],
            'metrics': m,
            'dataset': 'garystafford/deepfake-audio-detection v4',
            'n_train': int(len(y_train)),
            'n_test': int(len(y_test)),
        }
        path = os.path.join(MODELS_DIR, MODEL_FILES[name])
        joblib.dump(bundle, path)
        print(f'  -> {path}')

        if m['f1'] > best_f1:
            best_f1, best_name, best_pipeline = m['f1'], name, pipe

    # 3. 默认模型（兼容 voice_baseline.joblib）
    print(f'\n[3/4] 最佳模型: {MODEL_LABELS[best_name]} (F1={best_f1})')
    best_bundle = {
        'pipeline': best_pipeline,
        'feature_kind': 'delta',
        'n_mfcc': N_MFCC,
        'target_sr': TARGET_SR,
        'model_name': best_name,
        'model_label': MODEL_LABELS[best_name],
        'metrics': results[best_name],
        'dataset': 'garystafford/deepfake-audio-detection v4',
        'n_train': int(len(y_train)),
        'n_test': int(len(y_test)),
    }
    joblib.dump(best_bundle, os.path.join(MODELS_DIR, 'voice_baseline.joblib'))
    print('  -> models/voice_baseline.joblib（默认模型，=最佳模型）')

    # 4. 指标 + 图 + 报告
    print('\n[4/4] 写出指标与报告...')
    with open(os.path.join(STATS_DIR, 'voice_models_results.json'),
              'w', encoding='utf-8') as f:
        json.dump({
            'dataset': 'Deepfake Audio Detection v4',
            'source': 'garystafford/deepfake-audio-detection @ hf-mirror',
            'license': 'CC-BY-4.0',
            'feature_kind': 'delta',
            'n_mfcc': N_MFCC,
            'n_total': int(len(y)),
            'n_train': int(len(y_train)),
            'n_test': int(len(y_test)),
            'models': results,
            'best_model': best_name,
        }, f, ensure_ascii=False, indent=2)

    for name, m in results.items():
        plot_confusion_matrix(
            m['confusion_matrix'],
            f'Audio Deepfake Confusion Matrix: {name}',
            os.path.join(STATS_DIR, f'confusion_matrix_voice_{name}.png'))

    md = os.path.join(STATS_DIR, 'voice_models_summary.md')
    with open(md, 'w', encoding='utf-8') as f:
        f.write('# 语音深伪检测三模型对比报告（Deepfake Audio Detection v4）\n\n')
        f.write('## 数据集\n\n')
        f.write('- 名称：Deepfake Audio Detection Dataset v4'
                '（garystafford/deepfake-audio-detection，'
                'HuggingFace 镜像 hf-mirror.com 下载，CC-BY-4.0）\n')
        f.write(f'- 总样本：{len(y)} 条（真人 real {int((y==0).sum())} / '
                f'AI 合成 fake {int((y==1).sum())}），2.5~13 秒，16kHz FLAC\n')
        f.write('- 真人：YouTube 真人语音；合成：6 个 TTS/语音克隆平台生成\n')
        f.write(f'- 分层切分：训练 {len(y_train)} / 测试 {len(y_test)}（8:2）\n')
        f.write('- 特征：MFCC 均值 + Δ 均值 + ΔΔ 均值 = 60 维（n_mfcc=20）\n\n')
        f.write('## 测试集指标\n\n')
        f.write('| 模型 | Accuracy | Precision | Recall | F1 | 伪类 Recall |\n')
        f.write('|------|----------|-----------|--------|----|-------------|\n')
        for name, m in results.items():
            star = ' ⭐默认' if name == best_name else ''
            f.write(f"| {MODEL_LABELS[name]}{star} | {m['accuracy']} | "
                    f"{m['precision']} | {m['recall']} | {m['f1']} | "
                    f"{m['recall_fake']} |\n")
        f.write('\n> 三个模型文件分别为 `models/voice_gmm.joblib`、'
                '`voice_svm.joblib`、`voice_rf.joblib`，'
                '可在检测页面下拉选择；`voice_baseline.joblib` 指向最佳模型。\n')
    print(f'  -> {md}')
    print('\n训练完成。')


if __name__ == '__main__':
    main()
