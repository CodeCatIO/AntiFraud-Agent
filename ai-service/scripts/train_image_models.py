#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
图像真伪检测三模型训练脚本（CIFAKE 数据集）

数据集（网上下载，HuggingFace 镜像）:
  dragonintelligence/CIFAKE-image-dataset
  论文: CIFAKE: Image Classification and Explainable Identification of
  AI-Generated Synthetic Images (IEEE 2024)
  - 真(REAL): CIFAR-10 真实图像 60000 张
  - 伪(FAKE): Stable Diffusion 生成的对应图像 60000 张
  - 全部为 32x32 RGB JPEG
  本项目标签映射: CIFAKE label 1=REAL -> 0(真/正常); 0=FAKE -> 1(伪/风险)

输入:
  data/raw/cifake/{train,test}.parquet   列: image{bytes,path}, label
输出:
  - models/image_lr.joblib / image_rf.joblib / image_svm.joblib
    bundle: {pipeline, feature_kind, ela_quality, model_name, metrics, dataset}
  - models/image_baseline.joblib          三模型中测试集 F1 最高者（兼容默认推理路径）
  - data/image/processed/cifake_features.npz（特征缓存）
  - data/image/stats/image_models_results.json
  - data/image/stats/confusion_matrix_image_<model>.png
  - data/image/stats/image_models_summary.md

三个模型（特征统一为 full = ELA 8 维 + 颜色/噪声/边缘 19 维 + GLCM 4 维 = 31 维）:
  1. logistic_regression 逻辑回归
  2. random_forest       随机森林
  3. svm                 RBF 核支持向量机

用法:
  python train_image_models.py                  # 默认 4000/类训练, 1000/类测试
  python train_image_models.py --train-per-class 6000
"""
import os
import io
import json
import argparse
import warnings

import numpy as np
from PIL import Image
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
)
import joblib
import pyarrow.parquet as pq

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AI_SERVICE_DIR = os.path.dirname(SCRIPT_DIR)
RAW_DIR = os.path.join(AI_SERVICE_DIR, 'data', 'raw', 'cifake')
PROCESSED_DIR = os.path.join(AI_SERVICE_DIR, 'data', 'image', 'processed')
STATS_DIR = os.path.join(AI_SERVICE_DIR, 'data', 'image', 'stats')
MODELS_DIR = os.path.join(AI_SERVICE_DIR, 'models')

ELA_QUALITY = 90
RANDOM_STATE = 42
FEATURE_KIND = 'full'


# ============================================================
# 特征（与 anti_fraud_image.py / train_image_baseline.py 完全一致）
# ============================================================

def compute_ela_map(img_rgb_uint8, quality=ELA_QUALITY):
    pil_img = Image.fromarray(img_rgb_uint8.astype(np.uint8), mode='RGB')
    buf = io.BytesIO()
    pil_img.save(buf, 'JPEG', quality=quality)
    buf.seek(0)
    recompressed = np.array(Image.open(buf).convert('RGB'), dtype=np.float64)
    return np.abs(img_rgb_uint8.astype(np.float64) - recompressed)


def ela_features(ela_map):
    flat = ela_map.ravel()
    mean = float(np.mean(flat))
    std = float(np.std(flat))
    skew = float(np.mean(((flat - mean) / (std + 1e-8)) ** 3))
    return [
        mean, std, float(np.max(flat)), float(np.median(flat)),
        float(np.percentile(flat, 95)), float(np.percentile(flat, 99)),
        skew, float(np.mean(flat > 30)),
    ]


def glcm_features(gray, levels=16):
    import cv2
    g = (gray.astype(np.int32) // (256 // levels)).clip(0, levels - 1)
    g1 = g[:, :-1].ravel()
    g2 = g[:, 1:].ravel()
    glcm = np.zeros((levels, levels), dtype=np.float64)
    np.add.at(glcm, (g1, g2), 1)
    glcm += glcm.T
    total = glcm.sum()
    if total > 0:
        glcm /= total
    ii, jj = np.meshgrid(np.arange(levels), np.arange(levels), indexing='ij')
    contrast = float((glcm * (ii - jj) ** 2).sum())
    homogeneity = float((glcm / (1.0 + np.abs(ii - jj))).sum())
    energy = float((glcm ** 2).sum())
    mu_i = float((glcm * ii).sum())
    mu_j = float((glcm * jj).sum())
    std_i = float(np.sqrt((glcm * (ii - mu_i) ** 2).sum()))
    std_j = float(np.sqrt((glcm * (jj - mu_j) ** 2).sum()))
    correlation = float(
        (glcm * (ii - mu_i) * (jj - mu_j)).sum() / (std_i * std_j + 1e-10))
    return [contrast, homogeneity, energy, correlation]


def basic_features(img_rgb_uint8):
    import cv2
    img = img_rgb_uint8.astype(np.float64)
    gray = cv2.cvtColor(img_rgb_uint8, cv2.COLOR_RGB2GRAY)
    rgb_mean = [img[:, :, c].mean() for c in range(3)]
    rgb_std = [img[:, :, c].std() for c in range(3)]
    hsv = cv2.cvtColor(img_rgb_uint8, cv2.COLOR_RGB2HSV).astype(np.float64)
    hsv_mean = [hsv[:, :, c].mean() for c in range(3)]
    hsv_std = [hsv[:, :, c].std() for c in range(3)]
    brightness = float(gray.mean())
    contrast = float(gray.std())
    lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    edges = cv2.Canny(gray, 100, 200)
    edge_density = float((edges > 0).mean())
    denoised = cv2.medianBlur(gray, 3).astype(np.float64)
    noise = gray.astype(np.float64) - denoised
    return (rgb_mean + rgb_std + hsv_mean + hsv_std +
            [brightness, contrast, lap_var, edge_density,
             float(noise.mean()), float(noise.std()),
             float(np.abs(noise).mean())])


def extract_full_feature(jpeg_bytes):
    """解码一张 CIFAKE JPEG 并提取 full 特征 (31,)"""
    import cv2
    img_rgb = np.array(Image.open(io.BytesIO(jpeg_bytes)).convert('RGB'))
    ela_map = compute_ela_map(img_rgb)
    gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
    return (ela_features(ela_map) + basic_features(img_rgb) +
            glcm_features(gray))


# ============================================================
# 数据读取 / 特征缓存
# ============================================================

def _balanced_sample_indices(parquet_path, per_class, seed):
    """按 CIFAKE 原始标签分层抽样行号（0=FAKE,1=REAL 各 per_class 条）"""
    pf = pq.ParquetFile(parquet_path)
    labels = pf.read(columns=['label']).column('label').to_numpy()
    rng = np.random.RandomState(seed)
    idx = []
    for lab in (0, 1):
        cand = np.where(labels == lab)[0]
        if len(cand) < per_class:
            raise RuntimeError(
                f'{parquet_path} 中 label={lab} 仅 {len(cand)} 条，'
                f'不足 {per_class} 条')
        chosen = rng.choice(cand, size=per_class, replace=False)
        idx.append(chosen)
    idx = np.concatenate(idx)
    rng.shuffle(idx)
    return idx


def build_feature_matrix(parquet_path, per_class, seed):
    """抽样 -> 解码 -> 31 维特征。
    返回 X(n,31), y_project(n,)（项目标签：0 真 / 1 伪）"""
    idx = _balanced_sample_indices(parquet_path, per_class, seed)
    pf = pq.ParquetFile(parquet_path)
    # 按 100 行/row-group 批量读取，避免一次性载入全部图像字节
    needed = set(idx.tolist())
    img_bytes_by_row = {}
    for rg in range(pf.num_row_groups):
        start = rg * 100
        if any((start + k) in needed for k in range(100)):
            tbl = pf.read_row_group(rg)
            bcol = tbl.column('image').to_pylist()
            lcol = tbl.column('label').to_pylist()
            for k, (im, lab) in enumerate(zip(bcol, lcol)):
                r = start + k
                if r in needed:
                    img_bytes_by_row[r] = (im['bytes'], lab)

    feats, labels = [], []
    for r in idx:
        b, lab = img_bytes_by_row[r]
        feats.append(extract_full_feature(b))
        # CIFAKE: 0=FAKE -> 项目 1(伪); 1=REAL -> 项目 0(真)
        labels.append(1 - int(lab))
    return np.array(feats, dtype=np.float64), np.array(labels, dtype=np.int64)


def load_or_build_features(train_per_class, test_per_class, force=False):
    cache = os.path.join(PROCESSED_DIR, 'cifake_features.npz')
    if (not force) and os.path.exists(cache):
        z = np.load(cache)
        if (int(z['train_per_class']) == train_per_class and
                int(z['test_per_class']) == test_per_class):
            print(f'  使用特征缓存: {cache}')
            return z['X_train'], z['y_train'], z['X_test'], z['y_test']
        print('  抽样数量变化，重建特征...')

    print(f'  训练集抽样 {train_per_class}/类 ...')
    X_train, y_train = build_feature_matrix(
        os.path.join(RAW_DIR, 'train.parquet'), train_per_class, RANDOM_STATE)
    print(f'  测试集抽样 {test_per_class}/类 ...')
    X_test, y_test = build_feature_matrix(
        os.path.join(RAW_DIR, 'test.parquet'), test_per_class, RANDOM_STATE + 1)

    os.makedirs(PROCESSED_DIR, exist_ok=True)
    np.savez_compressed(
        cache, X_train=X_train, y_train=y_train,
        X_test=X_test, y_test=y_test,
        train_per_class=train_per_class, test_per_class=test_per_class)
    print(f'  特征缓存 -> {cache}')
    return X_train, y_train, X_test, y_test


# ============================================================
# 模型
# ============================================================

def build_model(name):
    if name == 'logistic_regression':
        return Pipeline([
            ('scaler', StandardScaler()),
            ('clf', LogisticRegression(
                C=1.0, max_iter=2000, random_state=RANDOM_STATE,
                class_weight='balanced')),
        ])
    if name == 'random_forest':
        return Pipeline([
            ('scaler', StandardScaler()),
            ('clf', RandomForestClassifier(
                n_estimators=300, max_depth=24, min_samples_leaf=2,
                random_state=RANDOM_STATE,
                class_weight='balanced', n_jobs=-1)),
        ])
    if name == 'svm':
        return Pipeline([
            ('scaler', StandardScaler()),
            ('clf', SVC(
                C=2.0, kernel='rbf', gamma='scale',
                probability=True, random_state=RANDOM_STATE,
                class_weight='balanced')),
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
    # 中文字体（Windows）
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'SimSun']
    plt.rcParams['axes.unicode_minus'] = False
    fig, ax = plt.subplots(figsize=(5, 4))
    im = ax.imshow(np.array(cm), interpolation='nearest', cmap=plt.cm.Blues)
    ax.set_title(title)
    fig.colorbar(im)
    classes = ['真(正常)', '伪(AI生成)']
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
    'logistic_regression': 'image_lr.joblib',
    'random_forest': 'image_rf.joblib',
    'svm': 'image_svm.joblib',
}
MODEL_LABELS = {
    'logistic_regression': '逻辑回归 LogisticRegression',
    'random_forest': '随机森林 RandomForest',
    'svm': '支持向量机 RBF-SVM',
}


def main():
    parser = argparse.ArgumentParser(description='CIFAKE 图像真伪三模型训练')
    parser.add_argument('--train-per-class', type=int, default=4000)
    parser.add_argument('--test-per-class', type=int, default=1000)
    parser.add_argument('--force-features', action='store_true',
                        help='忽略特征缓存强制重建')
    args = parser.parse_args()
    warnings.filterwarnings('ignore')

    print('=' * 60)
    print('图像真伪检测三模型训练（CIFAKE: REAL vs Stable-Diffusion FAKE）')
    print('=' * 60)

    os.makedirs(MODELS_DIR, exist_ok=True)
    os.makedirs(STATS_DIR, exist_ok=True)

    # 1. 数据与特征
    print('\n[1/4] 构建特征（ELA + 传统特征 + GLCM, 31 维）...')
    X_train, y_train, X_test, y_test = load_or_build_features(
        args.train_per_class, args.test_per_class, args.force_features)
    print(f'  X_train={X_train.shape}  X_test={X_test.shape}')
    print(f'  train 真/伪: {int((y_train==0).sum())}/{int((y_train==1).sum())}  '
          f'test 真/伪: {int((y_test==0).sum())}/{int((y_test==1).sum())}')

    # 2. 训练三模型
    results = {}
    best_name, best_f1, best_pipeline = None, -1.0, None
    for name in ('logistic_regression', 'random_forest', 'svm'):
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
            'feature_kind': FEATURE_KIND,
            'ela_quality': ELA_QUALITY,
            'model_name': name,
            'model_label': MODEL_LABELS[name],
            'metrics': m,
            'dataset': 'CIFAKE (dragonintelligence/CIFAKE-image-dataset)',
            'n_train': int(len(y_train)),
            'n_test': int(len(y_test)),
        }
        path = os.path.join(MODELS_DIR, MODEL_FILES[name])
        joblib.dump(bundle, path)
        print(f'  -> {path}')

        if m['f1'] > best_f1:
            best_f1, best_name, best_pipeline = m['f1'], name, pipe

    # 3. 默认模型（兼容 anti_fraud_image.py 的 image_baseline.joblib）
    print(f'\n[3/4] 最佳模型: {MODEL_LABELS[best_name]} (F1={best_f1})')
    best_bundle = {
        'pipeline': best_pipeline,
        'feature_kind': FEATURE_KIND,
        'ela_quality': ELA_QUALITY,
        'model_name': best_name,
        'model_label': MODEL_LABELS[best_name],
        'metrics': results[best_name],
        'dataset': 'CIFAKE (dragonintelligence/CIFAKE-image-dataset)',
        'n_train': int(len(y_train)),
        'n_test': int(len(y_test)),
    }
    joblib.dump(best_bundle, os.path.join(MODELS_DIR, 'image_baseline.joblib'))
    print('  -> models/image_baseline.joblib（默认模型，=最佳模型）')

    # 4. 指标 JSON + 混淆矩阵 + Markdown
    print('\n[4/4] 写出指标与报告...')
    os.makedirs(STATS_DIR, exist_ok=True)
    with open(os.path.join(STATS_DIR, 'image_models_results.json'),
              'w', encoding='utf-8') as f:
        json.dump({
            'dataset': 'CIFAKE',
            'source': 'dragonintelligence/CIFAKE-image-dataset @ hf-mirror',
            'feature_kind': FEATURE_KIND,
            'n_train': int(len(y_train)),
            'n_test': int(len(y_test)),
            'label_mapping': 'CIFAKE 0=FAKE->1(伪), 1=REAL->0(真)',
            'models': results,
            'best_model': best_name,
        }, f, ensure_ascii=False, indent=2)

    for name, m in results.items():
        plot_confusion_matrix(
            m['confusion_matrix'],
            f'CIFAKE Confusion Matrix: {name}',
            os.path.join(STATS_DIR, f'confusion_matrix_image_{name}.png'))

    md = os.path.join(STATS_DIR, 'image_models_summary.md')
    with open(md, 'w', encoding='utf-8') as f:
        f.write('# 图像真伪检测三模型对比报告（CIFAKE 数据集）\n\n')
        f.write('## 数据集\n\n')
        f.write('- 名称：CIFAKE（dragonintelligence/CIFAKE-image-dataset，'
                'HuggingFace 镜像 hf-mirror.com 下载）\n')
        f.write('- 论文：CIFAKE: Image Classification and Explainable '
                'Identification of AI-Generated Synthetic Images, IEEE 2024\n')
        f.write(f'- 训练抽样：{len(y_train)} 张（真/伪各 {args.train_per_class}）\n')
        f.write(f'- 测试抽样：{len(y_test)} 张（真/伪各 {args.test_per_class}）\n')
        f.write('- 标签：真=CIFAR-10 真实照片；伪=Stable Diffusion 生成图（32x32）\n')
        f.write('- 特征：ELA 误差统计(8) + 颜色/噪声/边缘(19) + GLCM 纹理(4) = 31 维\n\n')
        f.write('## 测试集指标\n\n')
        f.write('| 模型 | Accuracy | Precision | Recall | F1 | 伪类 Recall |\n')
        f.write('|------|----------|-----------|--------|----|-------------|\n')
        for name, m in results.items():
            star = ' ⭐默认' if name == best_name else ''
            f.write(f"| {MODEL_LABELS[name]}{star} | {m['accuracy']} | "
                    f"{m['precision']} | {m['recall']} | {m['f1']} | "
                    f"{m['recall_fake']} |\n")
        f.write('\n> 三个模型文件分别为 `models/image_lr.joblib`、'
                '`image_rf.joblib`、`image_svm.joblib`，'
                '可在检测页面下拉选择；`image_baseline.joblib` 指向最佳模型。\n')
    print(f'  -> {md}')
    print('\n训练完成。')


if __name__ == '__main__':
    main()
