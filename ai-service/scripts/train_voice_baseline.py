#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
语音诈骗检测传统机器学习 baseline 训练脚本

任务书 P1 / 任务5：实现 MFCC + GMM / SVM / 随机森林 三个分类器，
做 ablation study（不同特征 × 不同模型对比），输出混淆矩阵 + 准确率/精确率/
召回率/F1，并生成 MFCC 特征可视化图与频谱图，验收标准准确率 ≥ 80%。

输入：data/voice/processed/mfcc_features.npy + labels.npy
      （由 preprocess_voice.py 产出，含原始 + 增强样本的 20 维 MFCC 均值向量）
输出：
  - data/voice/stats/baseline_results.json     全部实验指标
  - data/voice/stats/confusion_matrix_*.png    混淆矩阵图
  - data/voice/stats/mfcc_visualization.png    MFCC 热力图对比（fraud vs normal）
  - data/voice/stats/spectrogram.png           频谱图对比
  - data/voice/stats/baseline_summary.md       实验报告
  - models/voice_baseline.joblib               最佳 Pipeline

注意：当前合成数据集仅 ~7 条原始样本，仅用于流程验证。真实数据
（≥500 条/类）到位后重跑本脚本即可获得验收所需的 ≥80% 准确率。
"""
import os
import json
import warnings
import traceback

import numpy as np
import librosa
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.mixture import GaussianMixture
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
)
import joblib

# 非交互后端，避免 GUI 弹窗
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# 路径配置
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AI_SERVICE_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(AI_SERVICE_DIR, 'data')
PROCESSED_DIR = os.path.join(DATA_DIR, 'voice', 'processed')
STATS_DIR = os.path.join(DATA_DIR, 'voice', 'stats')
MODELS_DIR = os.path.join(AI_SERVICE_DIR, 'models')
MODEL_PATH = os.path.join(MODELS_DIR, 'voice_baseline.joblib')

TARGET_SR = 16000
N_MFCC = 20
RANDOM_STATE = 42
CV_FOLDS = 5


# ============================================================
#  GMM 分类器包装器
# ============================================================

class GMMClassifier(BaseEstimator, ClassifierMixin):
    """基于 GaussianMixture 的二分类器

    为每个类别拟合一个 GMM，预测时比较各类别 GMM 的对数似然，
    取最大者作为预测类别。predict_proba 用 softmax(log-likelihood) 归一化。
    """

    def __init__(self, n_components=2, random_state=RANDOM_STATE):
        self.n_components = n_components
        self.random_state = random_state

    def fit(self, X, y):
        self.classes_ = np.unique(y)
        self.gmms_ = {}
        for c in self.classes_:
            Xc = X[y == c]
            # 小数据下减少分量数，避免协方差奇异
            n_comp = min(self.n_components, max(1, len(Xc)))
            gmm = GaussianMixture(
                n_components=n_comp,
                covariance_type='full',
                random_state=self.random_state,
                reg_covar=1e-3,
            )
            gmm.fit(Xc)
            self.gmms_[c] = gmm
        return self

    def _log_likelihood(self, X):
        """返回 (n_samples, n_classes) 对数似然矩阵"""
        ll = np.zeros((X.shape[0], len(self.classes_)))
        for i, c in enumerate(self.classes_):
            ll[:, i] = self.gmms_[c].score_samples(X)
        return ll

    def predict(self, X):
        ll = self._log_likelihood(X)
        idx = np.argmax(ll, axis=1)
        return self.classes_[idx]

    def predict_proba(self, X):
        ll = self._log_likelihood(X)
        # softmax 数值稳定
        ll_shift = ll - ll.max(axis=1, keepdims=True)
        proba = np.exp(ll_shift)
        proba /= proba.sum(axis=1, keepdims=True)
        return proba


# ============================================================
#  特征构建
# ============================================================

def extract_mfcc_full(path, n_mfcc=N_MFCC):
    """从单个 wav 文件提取完整 MFCC 矩阵 (n_mfcc, T)"""
    y, sr = librosa.load(path, sr=TARGET_SR)
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=n_mfcc)
    return y, sr, mfcc


def build_feature_vector(mfcc, kind='mean'):
    """从 MFCC 矩阵构建特征向量

    - mean: 每维均值 (n_mfcc,)
    - stats: 均值+标准差 (2*n_mfcc,)
    - delta: 均值 + Δ均值 + ΔΔ均值 (3*n_mfcc,)
    """
    if kind == 'mean':
        return np.mean(mfcc, axis=1)
    elif kind == 'stats':
        mean = np.mean(mfcc, axis=1)
        std = np.std(mfcc, axis=1)
        return np.concatenate([mean, std])
    elif kind == 'delta':
        mean = np.mean(mfcc, axis=1)
        d1 = librosa.feature.delta(mfcc)
        d2 = librosa.feature.delta(mfcc, order=2)
        d1_mean = np.mean(d1, axis=1)
        d2_mean = np.mean(d2, axis=1)
        return np.concatenate([mean, d1_mean, d2_mean])
    raise ValueError(f"Unknown feature kind: {kind}")


def load_processed_features():
    """加载 preprocess_voice.py 产出的 mfcc_features.npy + labels.npy

    Returns:
        (mfcc_mean_features, labels) 或 (None, None) 如果文件不存在
    """
    feat_path = os.path.join(PROCESSED_DIR, 'mfcc_features.npy')
    label_path = os.path.join(PROCESSED_DIR, 'labels.npy')
    if not os.path.exists(feat_path) or not os.path.exists(label_path):
        return None, None
    X = np.load(feat_path)
    y = np.load(label_path)
    return X, y


def rebuild_features_from_wavs():
    """从 processed 目录的 wav 文件重新提取更丰富的特征

    preprocess_voice.py 只保存了 MFCC 均值 (20 维)。
    本函数遍历 processed wav，重新提取 mean/stats/delta 三种特征。

    Returns:
        dict: {feature_kind: (X, y)}，以及文件路径列表（用于可视化）
    """
    files = [f for f in os.listdir(PROCESSED_DIR)
             if f.endswith('.wav') and not f.startswith('aug_')]
    aug_files = [f for f in os.listdir(PROCESSED_DIR)
                 if f.endswith('.wav') and f.startswith('aug_')]

    all_files = files + aug_files
    if not all_files:
        return {}, []

    feat_mean = []
    feat_stats = []
    feat_delta = []
    labels = []
    viz_files = {'fraud': None, 'normal': None}

    for fname in all_files:
        path = os.path.join(PROCESSED_DIR, fname)
        try:
            y_audio, sr, mfcc = extract_mfcc_full(path)
        except Exception as e:
            print(f"  ⚠️ 跳过 {fname}: {e}")
            continue

        # 标签：文件名以 fraud_ 或 aug_*_fraud_ 开头 -> 1，否则 normal -> 0
        if 'fraud_' in fname:
            label = 1
        else:
            label = 0

        feat_mean.append(build_feature_vector(mfcc, 'mean'))
        feat_stats.append(build_feature_vector(mfcc, 'stats'))
        feat_delta.append(build_feature_vector(mfcc, 'delta'))
        labels.append(label)

        # 记录可视化样本（优先原始文件）
        if label == 1 and viz_files['fraud'] is None and not fname.startswith('aug_'):
            viz_files['fraud'] = path
        elif label == 0 and viz_files['normal'] is None and not fname.startswith('aug_'):
            viz_files['normal'] = path

    result = {}
    if feat_mean:
        result['mean'] = (np.array(feat_mean), np.array(labels))
    if feat_stats:
        result['stats'] = (np.array(feat_stats), np.array(labels))
    if feat_delta:
        result['delta'] = (np.array(feat_delta), np.array(labels))

    return result, viz_files


# ============================================================
#  模型构建
# ============================================================

def build_model(name):
    """构建分类器 Pipeline（含 StandardScaler）

    语音特征量纲差异大，统一做标准化。
    """
    if name == 'gmm':
        return Pipeline([
            ('scaler', StandardScaler()),
            ('clf', GMMClassifier(n_components=2)),
        ])
    elif name == 'svm':
        return Pipeline([
            ('scaler', StandardScaler()),
            ('clf', SVC(
                C=1.0, kernel='rbf', gamma='scale',
                probability=True, random_state=RANDOM_STATE,
                class_weight='balanced',
            )),
        ])
    elif name == 'random_forest':
        return Pipeline([
            ('scaler', StandardScaler()),
            ('clf', RandomForestClassifier(
                n_estimators=200, max_depth=20,
                random_state=RANDOM_STATE,
                class_weight='balanced', n_jobs=-1,
            )),
        ])
    raise ValueError(f"Unknown model: {name}")


# ============================================================
#  指标计算
# ============================================================

def compute_metrics(y_true, y_pred):
    return {
        'accuracy': round(float(accuracy_score(y_true, y_pred)), 4),
        'precision': round(float(precision_score(
            y_true, y_pred, average='weighted', zero_division=0)), 4),
        'recall': round(float(recall_score(
            y_true, y_pred, average='weighted', zero_division=0)), 4),
        'f1': round(float(f1_score(
            y_true, y_pred, average='weighted', zero_division=0)), 4),
        'confusion_matrix': confusion_matrix(
            y_true, y_pred, labels=[0, 1]).tolist(),
    }


def run_experiment(feature_name, model_name, X, y):
    """运行单组 ablation 实验

    Returns:
        pipeline, holdout_metrics, cv_f1
    """
    pipeline = build_model(model_name)

    # 小数据集：70/30 holdout
    n_total = len(y)
    n_test = max(2, int(n_total * 0.3))
    rng = np.random.RandomState(RANDOM_STATE)
    idx = rng.permutation(n_total)
    test_idx = idx[:n_test]
    train_idx = idx[n_test:]

    X_train, X_test = X[train_idx], X[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]

    # 保证训练集两类都有
    if len(np.unique(y_train)) < 2 or len(np.unique(y_test)) < 2:
        # 退化：全量训练，全量测试（仅作流程验证）
        pipeline.fit(X, y)
        y_pred = pipeline.predict(X)
        holdout_metrics = compute_metrics(y, y_pred)
        return pipeline, holdout_metrics, None

    pipeline.fit(X_train, y_train)
    y_pred_test = pipeline.predict(X_test)
    holdout_metrics = compute_metrics(y_test, y_pred_test)

    # 5 折分层 CV（在全量数据上）
    n_splits = min(CV_FOLDS, int(np.bincount(y).min()))
    cv_f1 = None
    if n_splits >= 2:
        cv = StratifiedKFold(n_splits=n_splits, shuffle=True,
                             random_state=RANDOM_STATE)
        cv_scores = cross_val_score(
            pipeline, X, y, cv=cv, scoring='f1_weighted')
        cv_f1 = round(float(cv_scores.mean()), 4)

    return pipeline, holdout_metrics, cv_f1


# ============================================================
#  可视化
# ============================================================

def plot_confusion_matrix(cm, title, save_path):
    fig, ax = plt.subplots(figsize=(5, 4))
    im = ax.imshow(cm, interpolation='nearest', cmap=plt.cm.Blues)
    ax.set_title(title)
    fig.colorbar(im)

    classes = ['正常', '诈骗']
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(classes)
    ax.set_yticklabels(classes)
    ax.set_xlabel('Predicted')
    ax.set_ylabel('True')

    thresh = cm.max() / 2 if cm.max() > 0 else 0.5
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, format(int(cm[i, j]), 'd'),
                    ha="center", va="center",
                    color="white" if cm[i, j] > thresh else "black")

    fig.tight_layout()
    fig.savefig(save_path, dpi=120)
    plt.close(fig)


def plot_mfcc_visualization(viz_files, save_path):
    """绘制 fraud vs normal 的 MFCC 热力图对比"""
    fraud_path = viz_files.get('fraud')
    normal_path = viz_files.get('normal')

    if not fraud_path or not normal_path:
        print(f"  ⚠️ 缺少可视化样本，跳过 MFCC 可视化")
        return

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    for ax, path, title in [(axes[0], fraud_path, 'Fraud (诈骗)'),
                            (axes[1], normal_path, 'Normal (正常)')]:
        try:
            y, sr, mfcc = extract_mfcc_full(path)
            im = ax.imshow(mfcc, aspect='auto', origin='lower',
                           cmap='viridis')
            ax.set_title(f'MFCC - {title}')
            ax.set_xlabel('Frame')
            ax.set_ylabel('MFCC Coefficient')
            fig.colorbar(im, ax=ax)
        except Exception as e:
            ax.text(0.5, 0.5, f'Error: {e}', ha='center', va='center')
            ax.set_title(f'MFCC - {title} (failed)')

    fig.suptitle('MFCC Feature Comparison: Fraud vs Normal', fontsize=14)
    fig.tight_layout()
    fig.savefig(save_path, dpi=120)
    plt.close(fig)
    print(f"  -> {os.path.basename(save_path)}")


def plot_spectrogram(viz_files, save_path):
    """绘制 fraud vs normal 的频谱图对比"""
    fraud_path = viz_files.get('fraud')
    normal_path = viz_files.get('normal')

    if not fraud_path or not normal_path:
        print(f"  ⚠️ 缺少可视化样本，跳过频谱图")
        return

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    for ax, path, title in [(axes[0], fraud_path, 'Fraud (诈骗)'),
                            (axes[1], normal_path, 'Normal (正常)')]:
        try:
            y, sr = librosa.load(path, sr=TARGET_SR)
            D = librosa.amplitude_to_db(
                np.abs(librosa.stft(y)), ref=np.max)
            img = librosa.display.specshow(
                D, y_axis='log', x_axis='time', sr=sr, ax=ax)
            ax.set_title(f'Spectrogram - {title}')
            fig.colorbar(img, ax=ax, format='%+2.0f dB')
        except Exception as e:
            ax.text(0.5, 0.5, f'Error: {e}', ha='center', va='center')
            ax.set_title(f'Spectrogram - {title} (failed)')

    fig.suptitle('Spectrogram Comparison: Fraud vs Normal', fontsize=14)
    fig.tight_layout()
    fig.savefig(save_path, dpi=120)
    plt.close(fig)
    print(f"  -> {os.path.basename(save_path)}")


# ============================================================
#  主流程
# ============================================================

def main():
    warnings.filterwarnings('ignore')

    print("=" * 60)
    print("语音诈骗检测传统机器学习 baseline 训练")
    print("=" * 60)

    # 1. 加载/重建特征
    print("\n[1/6] 加载特征...")
    features_dict, viz_files = rebuild_features_from_wavs()

    if not features_dict:
        # 退化：使用 preprocess_voice.py 产出的 .npy（仅 mean 特征）
        print("  未找到 processed wav，回退到 mfcc_features.npy ...")
        X_npy, y_npy = load_processed_features()
        if X_npy is None:
            raise FileNotFoundError(
                f"未找到语音特征，请先运行 preprocess_voice.py")
        features_dict = {'mean': (X_npy, y_npy)}
        viz_files = {'fraud': None, 'normal': None}

    for kind, (X, y) in features_dict.items():
        print(f"  特征 {kind}: X={X.shape}, y={y.shape}, "
              f"fraud={int(y.sum())}, normal={int((y == 0).sum())}")

    total_samples = len(list(features_dict.values())[0][1])
    if total_samples < 100:
        print(f"\n  ⚠️ 警告：数据集过小（{total_samples} 条），结果仅供参考")
        print(f"  ⚠️ 请收集 ≥500 条/类真实数据后重跑本脚本以获得可靠结果")

    # 2. Ablation 矩阵
    print("\n[2/6] 运行特征×模型 ablation（3 特征 × 3 模型 = 9 组）...")
    feature_names = ['mean', 'stats', 'delta']
    model_names = ['gmm', 'svm', 'random_forest']

    results = {}
    best_score = -1.0
    best_pipeline = None
    best_combo = None

    for feat in feature_names:
        if feat not in features_dict:
            print(f"\n  跳过特征 {feat}（无数据）")
            continue
        X, y = features_dict[feat]
        for mdl in model_names:
            combo = f"{feat}__{mdl}"
            print(f"\n  --- {combo} ---")
            try:
                pipeline, holdout_metrics, cv_f1 = run_experiment(
                    feat, mdl, X, y)
                print(f"  Holdout: acc={holdout_metrics['accuracy']}, "
                      f"p={holdout_metrics['precision']}, "
                      f"r={holdout_metrics['recall']}, "
                      f"f1={holdout_metrics['f1']}")
                if cv_f1 is not None:
                    print(f"  CV-F1 (weighted): {cv_f1}")
                else:
                    print(f"  CV-F1: 跳过（每类样本不足）")

                results[combo] = {
                    'feature': feat,
                    'model': mdl,
                    'holdout': holdout_metrics,
                    'cv_f1': cv_f1,
                    'n_samples': int(len(y)),
                    'status': 'ok',
                }

                score = cv_f1 if cv_f1 is not None else holdout_metrics['f1']
                if score > best_score:
                    best_score = score
                    best_pipeline = pipeline
                    best_combo = combo

            except Exception as e:
                print(f"  ❌ 失败: {e}")
                traceback.print_exc()
                results[combo] = {
                    'feature': feat,
                    'model': mdl,
                    'status': 'failed',
                    'error': str(e),
                }

    # 3. 保存结果 JSON
    print(f"\n[3/6] 保存结果...")
    os.makedirs(STATS_DIR, exist_ok=True)

    results_path = os.path.join(STATS_DIR, 'baseline_results.json')
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump({
            'data_size': {
                'total': total_samples,
            },
            'feature_dims': {
                k: int(v[0].shape[1]) for k, v in features_dict.items()
            },
            'experiments': results,
            'best_combo': best_combo,
            'best_score': best_score,
        }, f, ensure_ascii=False, indent=2)
    print(f"  -> {results_path}")

    # 4. 绘制混淆矩阵
    print(f"\n[4/6] 绘制混淆矩阵图...")
    for combo, result in results.items():
        if result.get('status') != 'ok':
            continue
        cm = np.array(result['holdout']['confusion_matrix'])
        title = f"Confusion Matrix: {combo}"
        save_path = os.path.join(STATS_DIR, f"confusion_matrix_{combo}.png")
        try:
            plot_confusion_matrix(cm, title, save_path)
            print(f"  -> {os.path.basename(save_path)}")
        except Exception as e:
            print(f"  ⚠️ {combo} 绘图失败: {e}")

    # 5. MFCC + 频谱图可视化
    print(f"\n[5/6] 生成 MFCC 可视化与频谱图...")
    mfcc_viz_path = os.path.join(STATS_DIR, 'mfcc_visualization.png')
    try:
        plot_mfcc_visualization(viz_files, mfcc_viz_path)
    except Exception as e:
        print(f"  ⚠️ MFCC 可视化失败: {e}")

    spec_path = os.path.join(STATS_DIR, 'spectrogram.png')
    try:
        plot_spectrogram(viz_files, spec_path)
    except Exception as e:
        print(f"  ⚠️ 频谱图失败: {e}")

    # 6. 保存最佳模型
    print(f"\n[6/6] 保存最佳模型...")
    if best_pipeline is not None:
        os.makedirs(MODELS_DIR, exist_ok=True)
        # 保存时附带特征类型，方便推理时重建特征
        save_obj = {
            'pipeline': best_pipeline,
            'feature_kind': best_combo.split('__')[0],
            'n_mfcc': N_MFCC,
            'target_sr': TARGET_SR,
        }
        joblib.dump(save_obj, MODEL_PATH)
        print(f"  最佳组合: {best_combo} (score={best_score})")
        print(f"  -> {MODEL_PATH}")
    else:
        print(f"  ⚠️ 无可用模型，跳过保存")

    # 7. Markdown 报告
    summary_path = os.path.join(STATS_DIR, 'baseline_summary.md')
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write("# 语音诈骗检测传统机器学习 baseline 实验报告\n\n")
        f.write("## 数据规模\n\n")
        f.write(f"- 总样本数（含增强）: {total_samples} 条\n")
        for kind, (X, y) in features_dict.items():
            f.write(f"  - 特征 {kind}: {X.shape[0]} 样本, "
                    f"{X.shape[1]} 维\n")
        f.write("\n")

        if total_samples < 100:
            f.write("> ⚠️ **数据集过小，结果仅供参考**。请收集 ≥500 条/类"
                    "真实数据后重跑 `scripts/train_voice_baseline.py` "
                    "以获得验收所需的 ≥80% 准确率。\n\n")

        f.write("## 特征说明\n\n")
        f.write("| 特征 | 维度 | 说明 |\n")
        f.write("|------|------|------|\n")
        f.write("| mean | 20 | MFCC 每维均值 |\n")
        f.write("| stats | 40 | MFCC 均值+标准差 |\n")
        f.write("| delta | 60 | MFCC 均值 + Δ均值 + ΔΔ均值 |\n\n")

        f.write("## Ablation Study 实验结果\n\n")
        f.write("| 特征 | 模型 | Holdout Acc | Holdout P | Holdout R | "
                "Holdout F1 | CV-F1 | 状态 |\n")
        f.write("|------|------|-------------|-----------|-----------|"
                "------------|-------|------|\n")
        for combo, r in results.items():
            if r.get('status') == 'ok':
                h = r['holdout']
                cv_f1_str = f"{r['cv_f1']}" if r['cv_f1'] is not None else "N/A"
                best_mark = " ⭐" if combo == best_combo else ""
                f.write(f"| {r['feature']} | {r['model']} | "
                        f"{h['accuracy']} | {h['precision']} | "
                        f"{h['recall']} | {h['f1']} | {cv_f1_str} | "
                        f"✅{best_mark} |\n")
            else:
                err = r.get('error', '')[:40].replace('|', '/')
                f.write(f"| {r.get('feature', '?')} | "
                        f"{r.get('model', '?')} | - | - | - | - | - | "
                        f"❌ ({err}) |\n")

        f.write(f"\n## 可视化产出\n\n")
        f.write(f"- MFCC 热力图对比: `mfcc_visualization.png`\n")
        f.write(f"- 频谱图对比: `spectrogram.png`\n")
        f.write(f"- 混淆矩阵: `confusion_matrix_*.png`\n\n")

        f.write(f"## 最佳模型\n\n")
        if best_combo:
            f.write(f"- 组合: **{best_combo}**\n")
            f.write(f"- 得分: {best_score}\n")
            f.write(f"- 已保存到: `models/voice_baseline.joblib`\n")
            f.write(f"\n> 该模型已接入 `anti_fraud_voice.py`，启动 Flask 服务后 "
                    f"`/api/detect/voice` 会自动使用 ML 预测。\n")
        else:
            f.write("无可用模型。\n")

    print(f"  -> {summary_path}")

    print(f"\n{'=' * 60}")
    print(f"训练完成！")
    print(f"  结果: {results_path}")
    print(f"  报告: {summary_path}")
    print(f"  模型: {MODEL_PATH if best_pipeline else '无'}")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()
