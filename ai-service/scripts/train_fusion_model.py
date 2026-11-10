#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
多模态融合训练与评估脚本（任务7）
================================

在同一批对齐案例上，统一划分折（保证对比公平），评估：

单模态 baseline：
    text / voice / image（StandardScaler + LogisticRegression）
晚期融合（LateFusionClassifier）：
    stacking（元LR）/ mean / max / weighted（0.30/0.35/0.35）/ vote
早期融合：
    三模态特征拼接（51 维）+ LR / SVM

验收：融合 CV-F1/Acc 高于任何单模态；输出 0-100 风险分。

输入：data/multimodal/cases/（generate_multimodal_cases.py 产出）
输出：
  data/multimodal/stats/fusion_results.json
  data/multimodal/stats/fusion_summary.md
  data/multimodal/stats/confusion_matrix_*.png
  data/multimodal/stats/fusion_comparison.png   策略对比柱状图
  models/fusion_model.joblib
    {'late_estimator', 'score_meta', 'best_late_strategy', ...}

注意：当前为合成对齐数据（120 案例），用于验证融合机制与对比；
接入真实对齐报案数据（文本+通话+截图）后重跑本脚本即可。
"""
import os
import sys
import json
import warnings
import traceback

import numpy as np
from sklearn.base import clone
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import (
    accuracy_score, f1_score, confusion_matrix)
import joblib

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AI_SERVICE_DIR = os.path.dirname(SCRIPT_DIR)
if AI_SERVICE_DIR not in sys.path:
    sys.path.insert(0, AI_SERVICE_DIR)

from multimodal_features import (
    load_cases, build_feature_matrices, LateFusionClassifier,
)

DATA_DIR = os.path.join(AI_SERVICE_DIR, 'data')
CASES_DIR = os.path.join(DATA_DIR, 'multimodal', 'cases')
STATS_DIR = os.path.join(DATA_DIR, 'multimodal', 'stats')
MODELS_DIR = os.path.join(AI_SERVICE_DIR, 'models')
MODEL_PATH = os.path.join(MODELS_DIR, 'fusion_model.joblib')

RANDOM_STATE = 42
CV_FOLDS = 5


# ============================================================
#  统一折划分的手动 CV / holdout
# ============================================================

def _slice_late_X(X_late, idx):
    """对晚期融合的 dict X 按索引切片"""
    return {k: v[idx] for k, v in X_late.items()}


def evaluate_strategy(estimator, X, y, train_idx, test_idx):
    """holdout 评估

    Returns:
        metrics dict（acc/f1/confusion），fitted estimator
    """
    if isinstance(X, dict):
        est = clone(estimator)
        est.fit(_slice_late_X(X, train_idx), y[train_idx])
        y_pred = est.predict(_slice_late_X(X, test_idx))
    else:
        est = clone(estimator)
        est.fit(X[train_idx], y[train_idx])
        y_pred = est.predict(X[test_idx])

    return {
        'accuracy': round(float(accuracy_score(y[test_idx], y_pred)), 4),
        'f1': round(float(f1_score(y[test_idx], y_pred,
                                  average='weighted')), 4),
        'confusion_matrix': confusion_matrix(
            y[test_idx], y_pred, labels=[0, 1]).tolist(),
    }, est


def cv_evaluate(estimator, X, y):
    """手动 5 折 CV（折划分对所有策略一致）

    Returns:
        (mean_acc, mean_f1, per-fold list)
    """
    cv = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True,
                         random_state=RANDOM_STATE)
    folds = []
    for tr, te in cv.split(np.zeros(len(y)), y):
        if isinstance(X, dict):
            est = clone(estimator)
            est.fit(_slice_late_X(X, tr), y[tr])
            y_pred = est.predict(_slice_late_X(X, te))
        else:
            est = clone(estimator)
            est.fit(X[tr], y[tr])
            y_pred = est.predict(X[te])
        folds.append({
            'accuracy': round(float(accuracy_score(y[te], y_pred)), 4),
            'f1': round(float(f1_score(y[te], y_pred,
                                      average='weighted')), 4),
        })
    mean_acc = round(float(np.mean([f['accuracy'] for f in folds])), 4)
    mean_f1 = round(float(np.mean([f['f1'] for f in folds])), 4)
    return mean_acc, mean_f1, folds


# ============================================================
#  Estimator 工厂
# ============================================================

def single_modality_estimator():
    return Pipeline([
        ('scaler', StandardScaler()),
        ('clf', LogisticRegression(
            C=1.0, max_iter=1000, class_weight='balanced')),
    ])


def early_lr_estimator():
    return Pipeline([
        ('scaler', StandardScaler()),
        ('clf', LogisticRegression(
            C=1.0, max_iter=1000, class_weight='balanced')),
    ])


def early_svm_estimator():
    return Pipeline([
        ('scaler', StandardScaler()),
        ('clf', SVC(C=1.0, kernel='rbf', gamma='scale',
                    class_weight='balanced',
                    probability=True, random_state=RANDOM_STATE)),
    ])


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
    for i in range(2):
        for j in range(2):
            ax.text(j, i, format(int(cm[i, j]), 'd'),
                    ha="center", va="center",
                    color="white" if cm[i, j] > thresh else "black")
    fig.tight_layout()
    fig.savefig(save_path, dpi=120)
    plt.close(fig)


def plot_comparison_bar(results, order, save_path):
    """策略 CV 准确率/F1 分组柱状图"""
    names = order
    accs = [results[n]['cv_accuracy'] for n in names]
    f1s = [results[n]['cv_f1'] for n in names]

    x = np.arange(len(names))
    width = 0.38
    fig, ax = plt.subplots(figsize=(13, 5.5))
    b1 = ax.bar(x - width / 2, accs, width, label='CV Accuracy',
                color='#4C78A8')
    b2 = ax.bar(x + width / 2, f1s, width, label='CV F1',
                color='#F58518')

    # 分组分隔背景
    group_bounds = [2.5, 7.5]   # 3 单模态，5 晚期，2 早期
    for gb in group_bounds:
        ax.axvline(gb, color='gray', linestyle='--', alpha=0.5)

    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=30, ha='right')
    ax.set_ylim(0, 1.08)
    ax.set_ylabel('Score')
    ax.set_title('Single Modality vs Late Fusion vs Early Fusion '
                 '(5-fold CV)')
    ax.legend(loc='lower right')

    for bars in (b1, b2):
        for r in bars:
            h = r.get_height()
            ax.text(r.get_x() + r.get_width() / 2, h + 0.01,
                    f'{h:.2f}', ha='center', va='bottom', fontsize=8)

    fig.tight_layout()
    fig.savefig(save_path, dpi=130)
    plt.close(fig)


# ============================================================
#  主流程
# ============================================================

def main():
    warnings.filterwarnings('ignore')

    print("=" * 60)
    print("多模态融合训练与评估（任务7）")
    print("=" * 60)

    # 1. 加载对齐案例
    print("\n[1/5] 加载对齐案例...")
    cases = load_cases(CASES_DIR)
    if not cases:
        raise FileNotFoundError(
            f"无案例，请先运行 generate_multimodal_cases.py")

    Xt, Xv, Xi, Xearly, y = build_feature_matrices(cases)
    X_late = {'text': Xt, 'voice': Xv, 'image': Xi}
    print(f"  案例数: {len(y)}（诈骗 {int(y.sum())} / "
          f"正常 {int((y == 0).sum())}）")
    print(f"  特征: text {Xt.shape[1]}, voice {Xv.shape[1]}, "
          f"image {Xi.shape[1]}, early-concat {Xearly.shape[1]}")

    # 2. 统一 holdout 划分
    n_test = int(len(y) * 0.3)
    rng = np.random.RandomState(RANDOM_STATE)
    perm = rng.permutation(len(y))
    test_idx, train_idx = perm[:n_test], perm[n_test:]

    # 3. 全部策略
    print("\n[2/5] 构建并评估全部策略...")
    strategies = []

    # 单模态
    strategies.append(('single_text', single_modality_estimator(), Xt))
    strategies.append(('single_voice', single_modality_estimator(), Xv))
    strategies.append(('single_image', single_modality_estimator(), Xi))
    # 晚期融合
    for s in ('stacking', 'mean', 'max', 'weighted', 'vote'):
        strategies.append(
            (f'late_{s}', LateFusionClassifier(strategy=s), X_late))
    # 早期融合
    strategies.append(('early_lr', early_lr_estimator(), Xearly))
    strategies.append(('early_svm', early_svm_estimator(), Xearly))

    results = {}
    fitted_estimators = {}

    for name, est, X in strategies:
        print(f"\n  --- {name} ---")
        try:
            holdout, fitted = evaluate_strategy(
                est, X, y, train_idx, test_idx)
            cv_acc, cv_f1, folds = cv_evaluate(est, X, y)

            print(f"  Holdout: acc={holdout['accuracy']}, "
                  f"f1={holdout['f1']}")
            print(f"  CV: acc={cv_acc}, f1={cv_f1}")

            results[name] = {
                'holdout': holdout,
                'cv_accuracy': cv_acc,
                'cv_f1': cv_f1,
                'cv_folds': folds,
                'status': 'ok',
            }
            fitted_estimators[name] = fitted
        except Exception as e:
            print(f"  ❌ 失败: {e}")
            traceback.print_exc()
            results[name] = {'status': 'failed', 'error': str(e)}

    # 4. 选出最佳
    ok_names = [n for n, r in results.items() if r.get('status') == 'ok']
    best_name = max(ok_names, key=lambda n: results[n]['cv_f1'])

    # 单模态最佳（用于验收对比）
    single_names = [n for n in ok_names if n.startswith('single_')]
    best_single = max(single_names, key=lambda n: results[n]['cv_f1'])

    # 最佳晚期
    late_names = [n for n in ok_names if n.startswith('late_')]
    best_late = max(late_names, key=lambda n: results[n]['cv_f1'])

    print(f"\n[3/5] 最佳策略: {best_name} "
          f"(CV-F1={results[best_name]['cv_f1']})")
    print(f"  最佳单模态: {best_single} "
          f"(CV-F1={results[best_single]['cv_f1']})")
    gain = (results[best_name]['cv_f1']
            - results[best_single]['cv_f1'])
    print(f"  融合相对单模态 F1 提升: {round(gain, 4)}")

    # 5. 保存 JSON
    os.makedirs(STATS_DIR, exist_ok=True)
    results_path = os.path.join(STATS_DIR, 'fusion_results.json')
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump({
            'n_cases': int(len(y)),
            'experiments': results,
            'best_overall': best_name,
            'best_single_modality': best_single,
            'best_late_fusion': best_late,
            'f1_gain_vs_best_single': round(gain, 4),
        }, f, ensure_ascii=False, indent=2)
    print(f"\n[4/5] 结果 -> {results_path}")

    # 6. 混淆矩阵（3 单模态 + 最佳晚期 + 最佳早期，若不同）
    cm_targets = ['single_text', 'single_voice', 'single_image', best_late]
    early_best = max(
        [n for n in ok_names if n.startswith('early_')],
        key=lambda n: results[n]['cv_f1'])
    if early_best not in cm_targets:
        cm_targets.append(early_best)

    for name in cm_targets:
        if name in results and results[name].get('status') == 'ok':
            cm = np.array(results[name]['holdout']['confusion_matrix'])
            save_path = os.path.join(
                STATS_DIR, f"confusion_matrix_{name}.png")
            plot_confusion_matrix(cm, name, save_path)
            print(f"  -> confusion_matrix_{name}.png")

    # 7. 对比柱状图
    order = [n for n, _, _ in strategies]
    bar_path = os.path.join(STATS_DIR, 'fusion_comparison.png')
    plot_comparison_bar(results, order, bar_path)
    print(f"  -> fusion_comparison.png")

    # 8. 保存模型
    print(f"\n[5/5] 保存融合模型...")
    os.makedirs(MODELS_DIR, exist_ok=True)

    # 服务端 /api/assess/risk-multimodal 使用最佳晚期融合器
    late_estimator = fitted_estimators[best_late]
    # score-based risk_assessment 使用 stacking 元模型
    stacking_estimator = fitted_estimators.get('late_stacking')
    score_meta = stacking_estimator.meta_ if stacking_estimator else None

    bundle = {
        'late_estimator': late_estimator,
        'best_late_strategy': best_late.replace('late_', ''),
        'score_meta': score_meta,   # 输入 scores/100，输出融合概率
        'best_overall': best_name,
    }
    joblib.dump(bundle, MODEL_PATH)
    print(f"  -> {MODEL_PATH}")

    # 9. Markdown 报告
    summary_path = os.path.join(STATS_DIR, 'fusion_summary.md')
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write("# 多模态融合实验报告（任务7）\n\n")
        f.write("## 数据\n\n")
        f.write(f"- 对齐案例：{len(y)} 个（诈骗 {int(y.sum())} / "
                f"正常 {int((y == 0).sum())}）\n")
        f.write("- 每个模态以 25% 概率退化为中性不可信样本，"
                "模拟真实场景下单模态证据不足\n\n")

        f.write("## 实验结果（统一折划分，5 折 CV + 30% holdout）\n\n")
        f.write("| 策略 | 类型 | Holdout Acc | Holdout F1 | "
                "CV Acc | CV F1 |\n")
        f.write("|------|------|-------------|------------|"
                "--------|-------|\n")

        type_label = {}
        for n in ok_names:
            if n.startswith('single_'):
                type_label[n] = '单模态'
            elif n.startswith('late_'):
                type_label[n] = '晚期融合'
            else:
                type_label[n] = '早期融合'

        for n in order:
            if results[n].get('status') != 'ok':
                continue
            r = results[n]
            mark = ' ⭐' if n == best_name else ''
            f.write(f"| {n}{mark} | {type_label[n]} | "
                    f"{r['holdout']['accuracy']} | "
                    f"{r['holdout']['f1']} | {r['cv_accuracy']} | "
                    f"{r['cv_f1']} |\n")

        f.write(f"\n## 验收结论\n\n")
        f.write(f"- 最佳单模态：**{best_single}**，"
                f"CV-F1 = {results[best_single]['cv_f1']}\n")
        f.write(f"- 最佳融合策略：**{best_name}**，"
                f"CV-F1 = {results[best_name]['cv_f1']}\n")
        f.write(f"- F1 提升：**{round(gain, 4)}**\n")
        if gain > 0:
            f.write(f"\n✅ 融合评估优于任一单模态，满足任务7验收标准。"
                    f"原因：当某模态为中性/不可信时，其余模态仍可提供"
                    f"有效证据；仅当三模态同时不可信（数据集中 2/120）"
                    f"时融合才可能失效。\n")
        else:
            f.write("\n⚠️ 融合未优于单模态，请检查数据噪声设置。\n")

        f.write(f"\n## 融合方式说明\n\n")
        f.write("- **晚期融合**：各模态独立出 P(fraud)，"
                "再按规则/学习器组合，对模态缺失鲁棒、易部署\n")
        f.write("- **早期融合**：三模态特征拼接后统一分类，"
                "可建模模态间交互，但对缺失敏感、特征量纲需统一\n")
        f.write("- **注意力融合**（可选进阶）：在 P(fraud) 上学习 "
                "per-case 动态权重，数据量充足时可扩展\n\n")

        f.write("## 产出\n\n")
        f.write("- 模型: `models/fusion_model.joblib`\n")
        f.write("- 对比图: `fusion_comparison.png`\n")
        f.write("- 混淆矩阵: `confusion_matrix_*.png`\n")
        f.write("- score 型接口 /api/assess/risk 使用 stacking 元模型；"
                "文件型接口 /api/assess/risk-multimodal 使用完整晚期融合器\n")

    print(f"  -> {summary_path}")
    print(f"\n{'=' * 60}")
    print(f"完成：{best_name}，CV-F1={results[best_name]['cv_f1']}")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()
