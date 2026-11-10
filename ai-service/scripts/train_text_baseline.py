#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文本检测传统机器学习 baseline 训练脚本

任务书 P1 / 任务3：实现 TF-IDF + 朴素贝叶斯 / SVM / 随机森林 三个分类器，
做 ablation study（不同特征 × 不同模型对比），输出混淆矩阵 + 准确率/精确率/
召回率/F1，验收标准准确率 ≥ 85%。

输入：data/text/processed/{train,val,test}.csv（prepare_dataset.py 输出，列：content, label, category）
输出：
  - data/text/stats/baseline_results.json   全部实验指标
  - data/text/stats/confusion_matrix_*.png  混淆矩阵图
  - data/text/stats/baseline_summary.md     实验报告
  - reports/confusion_matrix_baseline.png   最佳模型混淆矩阵（任务5要求）
  - reports/baseline_metrics.json           最佳模型逐类指标（供报告引用）
  - models/text_baseline.joblib             最佳 Pipeline（anti_fraud_text.py 写死加载名）

数据：Telecom_Fraud_Texts_5（prepare_dataset.py 清洗切分后约 1.1 万条）。
"""
import os
import json
import time
import warnings
import traceback

import numpy as np
import pandas as pd
import jieba
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.naive_bayes import MultinomialNB
from sklearn.svm import LinearSVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, confusion_matrix,
    precision_recall_fscore_support
)
import joblib

# 非交互后端，避免 GUI 弹窗
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as _fm

for _fp in (r'C:\Windows\Fonts\msyh.ttc', r'C:\Windows\Fonts\simhei.ttf',
            r'C:\Windows\Fonts\simsun.ttc'):
    if os.path.exists(_fp):
        _fm.fontManager.addfont(_fp)
        plt.rcParams['font.sans-serif'] = [_fm.FontProperties(fname=_fp).get_name()]
        plt.rcParams['axes.unicode_minus'] = False
        break

# 路径配置
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AI_SERVICE_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(AI_SERVICE_DIR, 'data')
PROCESSED_DIR = os.path.join(DATA_DIR, 'text', 'processed')
STATS_DIR = os.path.join(DATA_DIR, 'text', 'stats')
REPORTS_DIR = os.path.join(AI_SERVICE_DIR, 'reports')
MODELS_DIR = os.path.join(AI_SERVICE_DIR, 'models')
MODEL_PATH = os.path.join(MODELS_DIR, 'text_baseline.joblib')


def tokenize_texts(texts):
    """jieba 分词，空格连接（与 anti_fraud_text.py 推理时的 tokens 构造方式一致）"""
    return [' '.join(jieba.cut(str(t))) for t in texts]

RANDOM_STATE = 42
CV_FOLDS = 5


def load_data():
    """加载 train/val/test CSV（prepare_dataset.py 输出：content,label,category），
    合并 train+val 作为训练集；内部生成 text/tokens 两列供 ColumnTransformer 使用。
    """
    def _load(name):
        df = pd.read_csv(os.path.join(PROCESSED_DIR, f'{name}.csv'))
        df['text'] = df['content'].fillna('').astype(str)
        df['tokens'] = tokenize_texts(df['text'])
        df['label'] = df['label'].astype(int)
        return df

    train = _load('train')
    val = _load('val')
    test = _load('test')
    train_val = pd.concat([train, val], ignore_index=True)
    return train_val, test


def build_feature(name):
    """构建特征 ColumnTransformer

    所有特征都接受 DataFrame 输入，按列名抽取。
    - word_*gram：对 tokens 列做词级 TF-IDF
    - char_*gram：对 text 列做字符级 TF-IDF
    - word_char_combined：FeatureUnion 等价（拼接 word + char）
    """
    if name == 'word_1gram':
        return ColumnTransformer([('word', TfidfVectorizer(
            analyzer='word', ngram_range=(1, 1),
            max_features=5000, min_df=1, max_df=0.95
        ), 'tokens')])
    elif name == 'word_12gram':
        return ColumnTransformer([('word', TfidfVectorizer(
            analyzer='word', ngram_range=(1, 2),
            max_features=10000, min_df=1, max_df=0.95
        ), 'tokens')])
    elif name == 'char_234gram':
        return ColumnTransformer([('char', TfidfVectorizer(
            analyzer='char_wb', ngram_range=(2, 4),
            max_features=5000, min_df=1, max_df=0.95
        ), 'text')])
    elif name == 'word_char_combined':
        return ColumnTransformer([
            ('word', TfidfVectorizer(
                analyzer='word', ngram_range=(1, 1),
                max_features=5000, min_df=1, max_df=0.95
            ), 'tokens'),
            ('char', TfidfVectorizer(
                analyzer='char_wb', ngram_range=(2, 4),
                max_features=5000, min_df=1, max_df=0.95
            ), 'text'),
        ])
    raise ValueError(f"Unknown feature: {name}")


def build_model(name):
    """构建分类器

    LinearSVC 用 CalibratedClassifierCV 包裹以提供 predict_proba，
    便于推理时输出诈骗概率。
    """
    if name == 'multinomial_nb':
        return MultinomialNB(alpha=1.0)
    elif name == 'linear_svc':
        return CalibratedClassifierCV(
            LinearSVC(C=1.0, max_iter=2000, class_weight='balanced', dual='auto'),
            cv=2, method='sigmoid'
        )
    elif name == 'random_forest':
        return RandomForestClassifier(
            n_estimators=200, max_depth=20, random_state=RANDOM_STATE,
            class_weight='balanced', n_jobs=-1
        )
    raise ValueError(f"Unknown model: {name}")


def compute_metrics(y_true, y_pred):
    """计算 accuracy/precision/recall/F1 + 混淆矩阵"""
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


def run_experiment(feature_name, model_name, train_val, test):
    """运行单组 ablation 实验

    Returns:
        pipeline, holdout_metrics, cv_f1
    """
    feature = build_feature(feature_name)
    model = build_model(model_name)
    pipeline = Pipeline([('feature', feature), ('model', model)])

    # 训练（train+val）
    X_train = train_val[['text', 'tokens']]
    y_train = train_val['label'].values
    pipeline.fit(X_train, y_train)

    # holdout 测试集
    X_test = test[['text', 'tokens']]
    y_test = test['label'].values
    y_pred_test = pipeline.predict(X_test)
    holdout_metrics = compute_metrics(y_test, y_pred_test)

    # 5 折分层 CV（在全部 train+val+test 上，因为数据量极小）
    full_data = pd.concat([train_val, test], ignore_index=True)
    X_full = full_data[['text', 'tokens']]
    y_full = full_data['label'].values

    n_splits = min(CV_FOLDS, int(np.bincount(y_full).min()))
    cv_f1 = None
    if n_splits >= 2:
        cv = StratifiedKFold(n_splits=n_splits, shuffle=True,
                             random_state=RANDOM_STATE)
        cv_scores = cross_val_score(
            pipeline, X_full, y_full, cv=cv, scoring='f1_weighted')
        cv_f1 = round(float(cv_scores.mean()), 4)

    return pipeline, holdout_metrics, cv_f1


def plot_confusion_matrix(cm, title, save_path):
    """绘制并保存混淆矩阵图"""
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


def main():
    warnings.filterwarnings('ignore')
    t_start = time.time()

    print("=" * 60)
    print("文本检测传统机器学习 baseline 训练")
    print("=" * 60)

    # 1. 加载数据
    print("\n[1/5] 加载数据...")
    train_val, test = load_data()
    print(f"  训练集(train+val): {len(train_val)} 条")
    print(f"  测试集: {len(test)} 条")

    if len(train_val) < 100:
        print(f"\n  ⚠️ 警告：数据集过小（{len(train_val)} 条），结果仅供参考")
        print(f"  ⚠️ 请收集 ≥5000 条真实数据后重跑本脚本以获得可靠结果")

    # 2. Ablation 矩阵
    print("\n[2/5] 运行特征×模型 ablation（4 特征 × 3 模型 = 12 组）...")
    features = ['word_1gram', 'word_12gram', 'char_234gram', 'word_char_combined']
    models = ['multinomial_nb', 'linear_svc', 'random_forest']

    results = {}
    best_score = -1.0
    best_pipeline = None
    best_combo = None

    for feat in features:
        for mdl in models:
            combo = f"{feat}__{mdl}"
            print(f"\n  --- {combo} ---")
            try:
                pipeline, holdout_metrics, cv_f1 = run_experiment(
                    feat, mdl, train_val, test)
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
                    'status': 'ok',
                }

                # 选最佳（优先 CV-F1，其次 holdout-F1）
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
    print(f"\n[3/5] 保存结果...")
    os.makedirs(STATS_DIR, exist_ok=True)

    results_path = os.path.join(STATS_DIR, 'baseline_results.json')
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump({
            'data_size': {
                'train_val': len(train_val),
                'test': len(test),
                'total': len(train_val) + len(test),
            },
            'experiments': results,
            'best_combo': best_combo,
            'best_score': best_score,
        }, f, ensure_ascii=False, indent=2)
    print(f"  -> {results_path}")

    # 4. 绘制混淆矩阵
    print(f"\n[4/5] 绘制混淆矩阵图...")
    y_test = test['label'].values
    test_has_both = len(np.unique(y_test)) == 2

    if test_has_both:
        for combo, result in results.items():
            if result.get('status') != 'ok':
                continue
            cm = np.array(result['holdout']['confusion_matrix'])
            title = f"Confusion Matrix: {combo}"
            save_path = os.path.join(
                STATS_DIR, f"confusion_matrix_{combo}.png")
            try:
                plot_confusion_matrix(cm, title, save_path)
                print(f"  -> {os.path.basename(save_path)}")
            except Exception as e:
                print(f"  ⚠️ {combo} 绘图失败: {e}")
    else:
        print(f"  ⚠️ 测试集仅含单一类别，跳过混淆矩阵图绘制")

    # 5. 保存最佳模型
    print(f"\n[5/5] 保存最佳模型...")
    elapsed_sec = round(time.time() - t_start, 1)
    if best_pipeline is not None:
        os.makedirs(MODELS_DIR, exist_ok=True)
        joblib.dump(best_pipeline, MODEL_PATH)
        print(f"  最佳组合: {best_combo} (score={best_score})")
        print(f"  -> {MODEL_PATH}")

        # 任务5要求：最佳模型逐类指标 + reports/ 混淆矩阵
        y_true = test['label'].values
        y_pred = best_pipeline.predict(test[['text', 'tokens']])
        p, r, f, s = precision_recall_fscore_support(
            y_true, y_pred, labels=[0, 1], zero_division=0)
        cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
        best_metrics = {
            'best_combo': best_combo,
            'selection_score_cv_f1': best_score,
            'training_seconds': elapsed_sec,
            'accuracy': round(float(accuracy_score(y_true, y_pred)), 4),
            'per_class': {
                '0_正常': {
                    'precision': round(float(p[0]), 4),
                    'recall': round(float(r[0]), 4),
                    'f1': round(float(f[0]), 4),
                    'support': int(s[0]),
                },
                '1_诈骗': {
                    'precision': round(float(p[1]), 4),
                    'recall': round(float(r[1]), 4),
                    'f1': round(float(f[1]), 4),
                    'support': int(s[1]),
                },
            },
            'confusion_matrix': cm.tolist(),
            'hyperparams': {
                'features': 'word(1-gram TF-IDF,5000) + char_wb(2-4gram TF-IDF,5000)'
                            if best_combo.startswith('word_char') else best_combo.split('__')[0],
                'classifier': best_combo.split('__')[1],
                'cv_folds': CV_FOLDS,
                'random_state': RANDOM_STATE,
            },
        }
        os.makedirs(REPORTS_DIR, exist_ok=True)
        with open(os.path.join(REPORTS_DIR, 'baseline_metrics.json'), 'w',
                  encoding='utf-8') as fout:
            json.dump(best_metrics, fout, ensure_ascii=False, indent=2)
        plot_confusion_matrix(
            cm, f'Baseline Best: {best_combo}',
            os.path.join(REPORTS_DIR, 'confusion_matrix_baseline.png'))
        print(f"  逐类指标/混淆矩阵 -> {REPORTS_DIR}")
    else:
        print(f"  ⚠️ 无可用模型，跳过保存")

    # 6. Markdown 报告
    summary_path = os.path.join(STATS_DIR, 'baseline_summary.md')
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write("# 文本检测传统机器学习 baseline 实验报告\n\n")
        f.write("## 数据规模\n\n")
        f.write(f"- 训练集(train+val): {len(train_val)} 条\n")
        f.write(f"- 测试集: {len(test)} 条\n")
        f.write(f"- 总计: {len(train_val) + len(test)} 条\n\n")

        if len(train_val) < 100:
            f.write("> ⚠️ **数据集过小，结果仅供参考**。请收集 ≥5000 条真实数据后"
                    "重跑 `scripts/train_text_baseline.py` 以获得验收所需的 ≥85% 准确率。\n\n")

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
                        f"{h['accuracy']} | {h['precision']} | {h['recall']} | "
                        f"{h['f1']} | {cv_f1_str} | ✅{best_mark} |\n")
            else:
                err = r.get('error', '')[:40].replace('|', '/')
                f.write(f"| {r.get('feature', '?')} | {r.get('model', '?')} | "
                        f"- | - | - | - | - | ❌ ({err}) |\n")

        f.write(f"\n## 最佳模型\n\n")
        if best_combo:
            f.write(f"- 组合: **{best_combo}**\n")
            f.write(f"- 得分: {best_score}\n")
            f.write(f"- 已保存到: `models/text_baseline.joblib`\n")
            f.write(f"\n> 该模型已接入 `anti_fraud_text.py`，启动 Flask 服务后 "
                    f"`/api/detect/text` 会自动使用 ML 预测。\n")
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
