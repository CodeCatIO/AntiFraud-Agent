#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
图像诈骗检测传统机器学习 baseline 训练脚本

任务书 P2 / 任务6：实现 ELA + 传统特征 + SVM，做 ablation study
（不同特征 × 不同模型对比），输出混淆矩阵 + 准确率/精确率/召回率/F1，
并生成 ELA 误差图可视化，验收标准真伪检测准确率 ≥ 85%。

二分类标签映射（真伪）：
    normal(0)  -> 0  真（正常图片）
    fraud(1) + tampered(2) -> 1  伪（诈骗截图/篡改图像）

输入：data/image/processed/ 下的 PNG（由 preprocess_image.py 产出，224x224）
输出：
  - data/image/stats/baseline_results.json    全部实验指标
  - data/image/stats/confusion_matrix_*.png   混淆矩阵图
  - data/image/stats/ela_visualization.png    ELA 误差图对比（伪 vs 真）
  - data/image/stats/sample_montage.png       样本示例拼图
  - data/image/stats/baseline_summary.md      实验报告
  - models/image_baseline.joblib              最佳 Pipeline

注意：当前合成数据集仅 12 条原始样本，仅用于流程验证。真实数据
（≥2000 张/类）到位后重跑本脚本即可获得验收所需的 ≥85% 准确率。
类激活图（CAM）可视化属于深度学习（ResNet）阶段，不在 baseline 范围。
"""
import os
import io
import json
import warnings
import traceback

import numpy as np
from PIL import Image
import cv2
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
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
PROCESSED_DIR = os.path.join(DATA_DIR, 'image', 'processed')
STATS_DIR = os.path.join(DATA_DIR, 'image', 'stats')
MODELS_DIR = os.path.join(AI_SERVICE_DIR, 'models')
MODEL_PATH = os.path.join(MODELS_DIR, 'image_baseline.joblib')

ELA_QUALITY = 90
RANDOM_STATE = 42
CV_FOLDS = 5


# ============================================================
#  ELA 特征
# ============================================================

def compute_ela_map(img_rgb_uint8, quality=ELA_QUALITY):
    """计算 ELA（Error Level Analysis）误差图

    将图像以指定 JPEG 质量重新保存，与原图做逐像素差分。
    篡改区域因经历过二次压缩，误差通常显著高于未篡改区域。

    Returns:
        np.ndarray (H, W, 3) float64 绝对误差
    """
    pil_img = Image.fromarray(img_rgb_uint8.astype(np.uint8), mode='RGB')
    buf = io.BytesIO()
    pil_img.save(buf, 'JPEG', quality=quality)
    buf.seek(0)
    recompressed = np.array(
        Image.open(buf).convert('RGB'), dtype=np.float64)
    diff = np.abs(img_rgb_uint8.astype(np.float64) - recompressed)
    return diff


def ela_features(ela_map):
    """ELA 图统计量（8 维）

    均值、标准差、最大值、中位数、95/99 分位数、偏度、
    高误差像素占比（>30 的像素比例）
    """
    flat = ela_map.ravel()
    mean = float(np.mean(flat))
    std = float(np.std(flat))
    mx = float(np.max(flat))
    med = float(np.median(flat))
    p95 = float(np.percentile(flat, 95))
    p99 = float(np.percentile(flat, 99))
    # 偏度（防除零）
    skew = float(np.mean(((flat - mean) / (std + 1e-8)) ** 3))
    high_ratio = float(np.mean(flat > 30))
    return [mean, std, mx, med, p95, p99, skew, high_ratio]


# ============================================================
#  GLCM 纹理特征（纯 numpy 实现，无需 skimage）
# ============================================================

def glcm_features(gray, levels=16):
    """灰度共生矩阵特征（水平方向，4 维）

    Returns:
        [contrast, homogeneity, energy, correlation]
    """
    g = (gray.astype(np.int32) // (256 // levels)).clip(0, levels - 1)
    g1 = g[:, :-1].ravel()
    g2 = g[:, 1:].ravel()

    glcm = np.zeros((levels, levels), dtype=np.float64)
    np.add.at(glcm, (g1, g2), 1)
    glcm += glcm.T  # 对称化
    total = glcm.sum()
    if total > 0:
        glcm /= total

    ii, jj = np.meshgrid(np.arange(levels), np.arange(levels),
                         indexing='ij')
    contrast = float((glcm * (ii - jj) ** 2).sum())
    homogeneity = float((glcm / (1.0 + np.abs(ii - jj))).sum())
    energy = float((glcm ** 2).sum())

    mu_i = float((glcm * ii).sum())
    mu_j = float((glcm * jj).sum())
    std_i = float(np.sqrt((glcm * (ii - mu_i) ** 2).sum()))
    std_j = float(np.sqrt((glcm * (jj - mu_j) ** 2).sum()))
    correlation = float(
        (glcm * (ii - mu_i) * (jj - mu_j)).sum() /
        (std_i * std_j + 1e-10))

    return [contrast, homogeneity, energy, correlation]


# ============================================================
#  基础传统特征
# ============================================================

def basic_features(img_rgb_uint8):
    """颜色 + 噪声 + 边缘统计（19 维）"""
    img = img_rgb_uint8.astype(np.float64)
    gray = cv2.cvtColor(img_rgb_uint8, cv2.COLOR_RGB2GRAY)

    # 1. RGB 各通道均值/标准差（6 维）
    rgb_mean = [img[:, :, c].mean() for c in range(3)]
    rgb_std = [img[:, :, c].std() for c in range(3)]

    # 2. HSV 各通道均值/标准差（6 维）
    hsv = cv2.cvtColor(img_rgb_uint8, cv2.COLOR_RGB2HSV).astype(np.float64)
    hsv_mean = [hsv[:, :, c].mean() for c in range(3)]
    hsv_std = [hsv[:, :, c].std() for c in range(3)]

    # 3. 亮度/对比度（2 维）
    brightness = float(gray.mean())
    contrast = float(gray.std())

    # 4. 拉普拉斯方差（1 维，检测模糊/AI 过度平滑）
    lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    # 5. 边缘密度（1 维）
    edges = cv2.Canny(gray, 100, 200)
    edge_density = float((edges > 0).mean())

    # 6. 噪声残差统计（3 维，中值滤波残差）
    denoised = cv2.medianBlur(gray, 3).astype(np.float64)
    noise = gray.astype(np.float64) - denoised
    noise_mean = float(noise.mean())
    noise_std = float(noise.std())
    noise_abs = float(np.abs(noise).mean())

    return (rgb_mean + rgb_std + hsv_mean + hsv_std +
            [brightness, contrast, lap_var, edge_density,
             noise_mean, noise_std, noise_abs])


# ============================================================
#  统一特征提取
# ============================================================

def extract_all_features(img_rgb_uint8):
    """提取全部特征组

    Returns:
        dict: {ela: 8, basic: 19, texture: 4}
    """
    ela_map = compute_ela_map(img_rgb_uint8)
    gray = cv2.cvtColor(img_rgb_uint8, cv2.COLOR_RGB2GRAY)
    return {
        'ela': ela_features(ela_map),
        'basic': basic_features(img_rgb_uint8),
        'texture': glcm_features(gray),
    }


def build_feature_vector(feat_dict, kind):
    """按特征组名拼接特征向量

    - ela:       ELA 统计（8）
    - basic:     颜色/噪声/边缘（19）
    - ela_basic: ELA + 基础（27）
    - full:      ELA + 基础 + GLCM 纹理（31）
    """
    if kind == 'ela':
        return feat_dict['ela']
    elif kind == 'basic':
        return feat_dict['basic']
    elif kind == 'ela_basic':
        return feat_dict['ela'] + feat_dict['basic']
    elif kind == 'full':
        return feat_dict['ela'] + feat_dict['basic'] + feat_dict['texture']
    raise ValueError(f"Unknown feature kind: {kind}")


def label_from_filename(fname):
    """从 processed 文件名推断二分类标签

    normal_*  -> 0（真）
    fraud_* / tampered_* / aug_*fraud* / aug_*tampered* -> 1（伪）
    """
    return 0 if 'normal' in fname else 1


# ============================================================
#  模型构建
# ============================================================

def build_model(name):
    """构建分类器 Pipeline（含 StandardScaler）"""
    if name == 'svm':
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
    elif name == 'logistic_regression':
        return Pipeline([
            ('scaler', StandardScaler()),
            ('clf', LogisticRegression(
                C=1.0, max_iter=1000, random_state=RANDOM_STATE,
                class_weight='balanced',
            )),
        ])
    raise ValueError(f"Unknown model: {name}")


# ============================================================
#  指标 + 实验
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


def run_experiment(model_name, X, y):
    """运行单组 ablation 实验：70/30 holdout + 5 折 CV"""
    pipeline = build_model(model_name)

    n_total = len(y)
    n_test = max(2, int(n_total * 0.3))
    rng = np.random.RandomState(RANDOM_STATE)
    idx = rng.permutation(n_total)
    test_idx = idx[:n_test]
    train_idx = idx[n_test:]

    X_train, X_test = X[train_idx], X[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]

    if len(np.unique(y_train)) < 2 or len(np.unique(y_test)) < 2:
        # 退化：全量训练 + 全量测试
        pipeline.fit(X, y)
        y_pred = pipeline.predict(X)
        return pipeline, compute_metrics(y, y_pred), None

    pipeline.fit(X_train, y_train)
    y_pred_test = pipeline.predict(X_test)
    holdout_metrics = compute_metrics(y_test, y_pred_test)

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

    classes = ['真(正常)', '伪(风险)']
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


def plot_ela_visualization(sample_paths, save_path):
    """绘制 ELA 误差图对比：伪 vs 真（2x2 网格）

    sample_paths: {'fake': path, 'real': path}
    """
    fig, axes = plt.subplots(2, 2, figsize=(11, 10))

    for row, (key, title) in enumerate(
            [('fake', 'Fake / 伪 (诈骗或篡改)'),
             ('real', 'Real / 真 (正常)')]):
        path = sample_paths.get(key)
        if not path or not os.path.exists(path):
            for col in range(2):
                axes[row][col].text(0.5, 0.5, 'No sample',
                                    ha='center', va='center')
            continue

        img = np.array(Image.open(path).convert('RGB'))
        ela_map = compute_ela_map(img)
        # 放大显示：每通道最大值归一化，再整体取幅度
        ela_amp = ela_map.max(axis=2)
        ela_norm = ela_amp / (ela_amp.max() + 1e-8) * 255

        axes[row][0].imshow(img)
        axes[row][0].set_title(f'Original - {title}')
        axes[row][0].axis('off')

        im = axes[row][1].imshow(ela_norm, cmap='hot', vmin=0, vmax=255)
        axes[row][1].set_title(f'ELA Map - {title}')
        axes[row][1].axis('off')
        fig.colorbar(im, ax=axes[row][1], fraction=0.046)

    fig.suptitle('Error Level Analysis (ELA): Fake vs Real', fontsize=14)
    fig.tight_layout()
    fig.savefig(save_path, dpi=120)
    plt.close(fig)
    print(f"  -> {os.path.basename(save_path)}")


def plot_sample_montage(sample_paths, save_path):
    """样本示例拼图：fraud / tampered / normal 各一张"""
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.5))
    items = [
        ('fraud', 'Fraud Screenshot 诈骗截图'),
        ('tampered', 'Tampered 篡改图像'),
        ('normal', 'Normal 正常图片'),
    ]
    for ax, (key, title) in zip(axes, items):
        path = sample_paths.get(key)
        if path and os.path.exists(path):
            ax.imshow(np.array(Image.open(path).convert('RGB')))
        else:
            ax.text(0.5, 0.5, 'No sample', ha='center', va='center')
        ax.set_title(title)
        ax.axis('off')

    fig.suptitle('Image Dataset Samples', fontsize=14)
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
    print("图像诈骗检测传统机器学习 baseline 训练")
    print("=" * 60)

    # 1. 扫描 processed PNG
    print("\n[1/6] 扫描 processed 图片并提取特征...")
    if not os.path.isdir(PROCESSED_DIR):
        raise FileNotFoundError(
            f"目录不存在: {PROCESSED_DIR}，请先运行 preprocess_image.py")

    all_files = [f for f in os.listdir(PROCESSED_DIR)
                 if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    if not all_files:
        raise FileNotFoundError("processed 目录无图片，请先运行预处理")

    # 每类原始样本（用于可视化，非 aug 开头）
    orig_samples = {'fraud': None, 'tampered': None, 'normal': None}

    feat_cache = {}   # fname -> feature dict
    labels = {}
    counts = {'fake': 0, 'real': 0}

    for fname in all_files:
        path = os.path.join(PROCESSED_DIR, fname)
        img = np.array(Image.open(path).convert('RGB'))
        feat_dict = extract_all_features(img)
        feat_cache[fname] = feat_dict

        y = label_from_filename(fname)
        labels[fname] = y
        counts['fake' if y == 1 else 'real'] += 1

        # 记录原始样本
        if not fname.startswith('aug_'):
            for key in orig_samples:
                if fname.startswith(key + '_') and orig_samples[key] is None:
                    orig_samples[key] = path

    print(f"  共 {len(all_files)} 张：真(正常)={counts['real']}, "
          f"伪(诈骗/篡改)={counts['fake']}")

    total_samples = len(all_files)
    if total_samples < 100:
        print(f"\n  ⚠️ 警告：数据集过小（{total_samples} 张），结果仅供参考")
        print(f"  ⚠️ 请收集 ≥2000 张/类真实数据后重跑本脚本以获得可靠结果")

    # 2. 构建 4 种特征矩阵
    print("\n[2/6] 构建特征矩阵...")
    feature_kinds = ['ela', 'basic', 'ela_basic', 'full']
    matrices = {}
    fnames_sorted = sorted(all_files)
    for kind in feature_kinds:
        X = np.array([
            build_feature_vector(feat_cache[f], kind) for f in fnames_sorted
        ])
        y = np.array([labels[f] for f in fnames_sorted])
        matrices[kind] = (X, y)
        print(f"  {kind}: {X.shape}")

    # 3. Ablation：4 特征 × 3 模型 = 12 组
    print("\n[3/6] 运行特征×模型 ablation（4 特征 × 3 模型 = 12 组）...")
    model_names = ['svm', 'random_forest', 'logistic_regression']

    results = {}
    best_score = -1.0
    best_pipeline = None
    best_combo = None
    best_feature_kind = None

    for feat in feature_kinds:
        X, y = matrices[feat]
        for mdl in model_names:
            combo = f"{feat}__{mdl}"
            print(f"\n  --- {combo} ---")
            try:
                pipeline, holdout_metrics, cv_f1 = run_experiment(mdl, X, y)
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
                    best_feature_kind = feat

            except Exception as e:
                print(f"  ❌ 失败: {e}")
                traceback.print_exc()
                results[combo] = {
                    'feature': feat,
                    'model': mdl,
                    'status': 'failed',
                    'error': str(e),
                }

    # 4. 保存结果 JSON
    print(f"\n[4/6] 保存结果...")
    os.makedirs(STATS_DIR, exist_ok=True)

    results_path = os.path.join(STATS_DIR, 'baseline_results.json')
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump({
            'data_size': {
                'total': total_samples,
                'real': counts['real'],
                'fake': counts['fake'],
            },
            'feature_dims': {k: int(v[0].shape[1])
                             for k, v in matrices.items()},
            'experiments': results,
            'best_combo': best_combo,
            'best_score': best_score,
        }, f, ensure_ascii=False, indent=2)
    print(f"  -> {results_path}")

    # 5. 混淆矩阵
    print(f"\n[5/6] 绘制混淆矩阵图...")
    for combo, result in results.items():
        if result.get('status') != 'ok':
            continue
        cm = np.array(result['holdout']['confusion_matrix'])
        save_path = os.path.join(STATS_DIR, f"confusion_matrix_{combo}.png")
        try:
            plot_confusion_matrix(cm, f"Confusion Matrix: {combo}", save_path)
            print(f"  -> {os.path.basename(save_path)}")
        except Exception as e:
            print(f"  ⚠️ {combo} 绘图失败: {e}")

    # 6. ELA 可视化 + 样本拼图
    print(f"\n[6/6] 生成 ELA 可视化与样本拼图...")
    ela_viz_path = os.path.join(STATS_DIR, 'ela_visualization.png')
    sample_paths = {
        'fake': orig_samples['fraud'] or orig_samples['tampered'],
        'real': orig_samples['normal'],
    }
    try:
        plot_ela_visualization(sample_paths, ela_viz_path)
    except Exception as e:
        print(f"  ⚠️ ELA 可视化失败: {e}")

    montage_path = os.path.join(STATS_DIR, 'sample_montage.png')
    try:
        plot_sample_montage(orig_samples, montage_path)
    except Exception as e:
        print(f"  ⚠️ 样本拼图失败: {e}")

    # 7. 保存最佳模型
    print(f"\n保存最佳模型...")
    if best_pipeline is not None:
        os.makedirs(MODELS_DIR, exist_ok=True)
        save_obj = {
            'pipeline': best_pipeline,
            'feature_kind': best_feature_kind,
            'ela_quality': ELA_QUALITY,
        }
        joblib.dump(save_obj, MODEL_PATH)
        print(f"  最佳组合: {best_combo} (score={best_score})")
        print(f"  -> {MODEL_PATH}")
    else:
        print(f"  ⚠️ 无可用模型，跳过保存")

    # 8. Markdown 报告
    summary_path = os.path.join(STATS_DIR, 'baseline_summary.md')
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write("# 图像诈骗检测传统机器学习 baseline 实验报告\n\n")
        f.write("## 数据规模\n\n")
        f.write(f"- 总样本数（含增强）: {total_samples} 张\n")
        f.write(f"- 真（正常）: {counts['real']} 张\n")
        f.write(f"- 伪（诈骗截图/篡改）: {counts['fake']} 张\n\n")

        if total_samples < 100:
            f.write("> ⚠️ **数据集过小，结果仅供参考**。请收集 ≥2000 张/类"
                    "真实数据后重跑 `scripts/train_image_baseline.py` "
                    "以获得验收所需的 ≥85% 准确率。\n\n")

        f.write("## 特征说明\n\n")
        f.write("| 特征组 | 维度 | 说明 |\n")
        f.write("|--------|------|------|\n")
        f.write("| ela | 8 | ELA 误差图统计（均值/方差/分位数/偏度等）|\n")
        f.write("| basic | 19 | RGB/HSV 统计 + 亮度对比度 + 拉普拉斯"
                "+ 边缘密度 + 噪声残差 |\n")
        f.write("| ela_basic | 27 | ELA + 基础特征 |\n")
        f.write("| full | 31 | ELA + 基础 + GLCM 纹理特征 |\n\n")

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
        f.write(f"- ELA 误差图对比: `ela_visualization.png`\n")
        f.write(f"- 样本示例拼图: `sample_montage.png`\n")
        f.write(f"- 混淆矩阵: `confusion_matrix_*.png`\n\n")

        f.write(f"## 最佳模型\n\n")
        if best_combo:
            f.write(f"- 组合: **{best_combo}**\n")
            f.write(f"- 得分: {best_score}\n")
            f.write(f"- 已保存到: `models/image_baseline.joblib`\n")
            f.write(f"\n> 该模型已接入 `anti_fraud_image.py`，启动 Flask 服务后 "
                    f"`/api/detect/image` 会自动使用 ML 预测。\n")
            f.write(f"\n> 注：类激活图（CAM）可视化属于深度学习"
                    f"（ResNet/EfficientNet）阶段，不在 baseline 范围。\n")
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
