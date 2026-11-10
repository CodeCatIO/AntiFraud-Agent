#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文本检测模型对比报告生成器（任务4 实验对比）

汇总三组实验结果：
  - 传统 ML baseline (12 组 ablation，来自 train_text_baseline.py)
  - TextCNN (来自 train_text_cnn.py)
  - BiLSTM+Attention (来自 train_text_bilstm.py)

输出：
  - data/text/stats/deep_learning_comparison.json    (结构化数据)
  - data/text/stats/deep_learning_comparison.md      (论文素材 markdown)

任务书验收：
  - 准确率 ≥ 92%（深度学习目标）
  - 比传统方法有明显提升（≥5%）
  - 有实验对比表格和分析
"""
import os
import json
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AI_SERVICE_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(AI_SERVICE_DIR, 'data')
STATS_DIR = os.path.join(DATA_DIR, 'text', 'stats')
MODEL_DIR = os.path.join(AI_SERVICE_DIR, 'models')


def load_baseline_results() -> dict:
    """加载传统 ML baseline 结果"""
    path = os.path.join(STATS_DIR, 'baseline_results.json')
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_dl_results(name: str) -> dict:
    """加载深度学习模型结果"""
    path = os.path.join(STATS_DIR, f'{name}_results.json')
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _baseline_summary(baseline: dict) -> dict:
    """从 baseline_results.json 提取最佳 + 平均"""
    if not baseline:
        return {'available': False}
    experiments = baseline.get('experiments', {})
    rows = []
    for key, exp in experiments.items():
        if 'error' in exp or 'cv_metrics' not in exp:
            continue
        cv = exp['cv_metrics']
        holdout = exp.get('holdout_metrics', {})
        rows.append({
            'name': key,
            'feature': exp.get('feature', ''),
            'model': exp.get('model', ''),
            'cv_f1': cv.get('f1', 0),
            'cv_acc': cv.get('acc', 0),
            'holdout_f1': holdout.get('f1', 0),
            'holdout_acc': holdout.get('acc', 0),
        })
    if not rows:
        return {'available': False}
    best_cv = max(rows, key=lambda r: r['cv_f1'])
    best_holdout = max(rows, key=lambda r: r['holdout_f1'])
    avg_cv_f1 = sum(r['cv_f1'] for r in rows) / len(rows)
    return {
        'available': True,
        'total_experiments': len(rows),
        'rows': rows,
        'best_by_cv_f1': best_cv,
        'best_by_holdout_f1': best_holdout,
        'avg_cv_f1': avg_cv_f1,
    }


def generate_markdown(baseline: dict, cnn: dict, bilstm: dict) -> str:
    """生成对比 markdown 报告（论文素材）"""
    lines = []
    lines.append("# 文本诈骗检测模型对比实验报告\n")
    lines.append("> 任务4：深度学习与传统机器学习方法的实验对比\n")
    lines.append("> 数据集：211 条真实+合成样本（train=147 / val=42 / test=22）\n")

    # === 1. 实验设置 ===
    lines.append("\n## 1. 实验设置\n")
    lines.append("| 维度 | 配置 |\n|---|---|")
    lines.append("| 数据集 | 文本诈骗检测（CSV，列 text,label） |")
    lines.append("| 划分 | 7:2:1（train/val/test） |")
    lines.append("| 评估指标 | Accuracy / Precision / Recall / F1（weighted）+ 混淆矩阵 |")
    lines.append("| 实验框架 | scikit-learn（传统 ML）+ PyTorch（深度学习） |")
    lines.append("| 随机种子 | 42（保证可复现） |")

    # === 2. 传统 ML baseline 汇总 ===
    lines.append("\n## 2. 传统机器学习 baseline（任务3）\n")
    bs = _baseline_summary(baseline)
    if not bs.get('available'):
        lines.append("> 未找到传统 ML baseline 结果，请先运行 `train_text_baseline.py`。\n")
    else:
        lines.append(f"\n共 {bs['total_experiments']} 组 ablation（4 特征 × 3 模型）：\n")
        lines.append("\n| # | 特征 | 模型 | CV-F1 | CV-Acc | Holdout-F1 | Holdout-Acc |")
        lines.append("\n|---|---|---|---|---|---|---|")
        for i, r in enumerate(sorted(bs['rows'], key=lambda x: -x['cv_f1']), 1):
            lines.append(f"\n| {i} | {r['feature']} | {r['model']} | "
                         f"{r['cv_f1']:.4f} | {r['cv_acc']:.4f} | "
                         f"{r['holdout_f1']:.4f} | {r['holdout_acc']:.4f} |")
        lines.append(f"\n**最佳（按 CV-F1）**: {bs['best_by_cv_f1']['feature']} + "
                     f"{bs['best_by_cv_f1']['model']}，CV-F1 = {bs['best_by_cv_f1']['cv_f1']:.4f}")
        lines.append(f"\n**平均 CV-F1**: {bs['avg_cv_f1']:.4f}")

    # === 3. 深度学习结果 ===
    lines.append("\n## 3. 深度学习模型（任务4）\n")
    for name, res in [('TextCNN', cnn), ('BiLSTM+Attention', bilstm)]:
        if not res:
            lines.append(f"\n### {name}\n> 未找到结果，请先运行对应训练脚本。\n")
            continue
        cfg = res.get('config', {})
        m = res.get('test_metrics', {})
        lines.append(f"\n### {name}\n")
        lines.append(f"- 配置: embed_dim={cfg.get('embed_dim')} "
                     f"max_len={cfg.get('max_len')} dropout={cfg.get('dropout')} "
                     f"epochs_run={cfg.get('epochs_run')}\n")
        lines.append(f"- 参数量（训练后写入 meta，此处略）\n")
        lines.append(f"- **测试集指标**: Acc={m.get('acc',0):.4f} "
                     f"P={m.get('precision',0):.4f} R={m.get('recall',0):.4f} "
                     f"F1={m.get('f1',0):.4f}\n")
        cm = m.get('confusion_matrix')
        labels = m.get('labels', [])
        if cm and labels:
            lines.append(f"- 混淆矩阵（labels={labels}）: {cm}\n")
        bv = res.get('best_val_f1', 0)
        lines.append(f"- 最佳验证 F1: {bv:.4f}\n")

    # === 4. 对比与结论 ===
    lines.append("\n## 4. 三类方法对比\n")
    rows = []
    if bs.get('available'):
        b = bs['best_by_cv_f1']
        rows.append(('传统ML最佳', f"{b['feature']}+{b['model']}",
                     b['cv_f1'], b['holdout_acc']))
    for name, res in [('TextCNN', cnn), ('BiLSTM+Attention', bilstm)]:
        if res:
            m = res.get('test_metrics', {})
            rows.append((name, res.get('config', {}).get('model_type', name),
                         res.get('best_val_f1', 0), m.get('acc', 0)))

    if rows:
        lines.append("\n| 方法 | 模型 | 最佳Val-F1 | Test-Acc |\n|---|---|---|---|")
        for r in rows:
            lines.append(f"\n| {r[0]} | {r[1]} | {r[2]:.4f} | {r[3]:.4f} |")

        # 提升幅度
        if len(rows) >= 2:
            base_acc = rows[0][3]
            lines.append("\n### 提升分析\n")
            for label, _, _, acc in rows[1:]:
                delta = (acc - base_acc) * 100
                lines.append(f"- {label} vs 传统ML最佳: Test-Acc 提升 **{delta:+.2f}%**\n")

    # === 5. 验收对照 ===
    lines.append("\n## 5. 验收标准对照（任务书）\n")
    lines.append("| 项目 | 标准 | 实际 | 结论 |\n|---|---|---|---|")
    best_test_acc = max([r[3] for r in rows], default=0)
    target_acc = 0.92
    lines.append(f"\n| 深度学习准确率 | ≥ {target_acc*100:.0f}% | {best_test_acc*100:.2f}% | "
                 f"{'✅ 达标' if best_test_acc >= target_acc else '⚠️ 未达标（数据量小，需扩数据集）'} |")
    if len(rows) >= 2:
        delta = (rows[1][3] - rows[0][3]) * 100
        target_delta = 5
        lines.append(f"\n| 比传统方法提升 | ≥ {target_delta}% | {delta:+.2f}% | "
                     f"{'✅ 达标' if delta >= target_delta else '⚠️ 未达标（数据量小）'} |")
    lines.append("\n| 实验对比与分析 | 有 | 已提供对比表+提升分析 | ✅ |\n")

    lines.append("\n## 6. 分析与后续改进\n")
    lines.append("- **当前数据规模**：211 条（含 198 条 Kaggle SMS + 3 条中文模板 + 10 条合成）。"
                 "深度学习需 ≥5000 条才能稳定达到 ≥92% 准确率。\n")
    lines.append("- **提升路径**：\n")
    lines.append("  1. 扩充数据集到 ≥5000 条（任务书最低要求）\n")
    lines.append("  2. 引入预训练中文 BERT/RoBERTa（需安装 transformers）\n")
    lines.append("  3. 调超参：embed_dim=256, hidden=256, lr=5e-4, epochs=50\n")
    lines.append("  4. 加入 focal loss 处理类别不均衡\n")
    lines.append("- **可复现性**：所有训练脚本支持 `--seed 42`，模型权重与词表已保存到 `models/`。\n")
    return ''.join(lines)


def main():
    parser = argparse.ArgumentParser(description='文本模型对比报告')
    parser.add_argument('--open', action='store_true', help='生成后输出报告路径')
    args = parser.parse_args()

    print("=" * 60)
    print("生成文本模型对比报告")
    print("=" * 60)

    baseline = load_baseline_results()
    cnn = load_dl_results('text_cnn')
    bilstm = load_dl_results('text_bilstm')

    print(f"  传统 ML baseline: {'已加载' if baseline else '缺失'}")
    print(f"  TextCNN:          {'已加载' if cnn else '缺失'}")
    print(f"  BiLSTM+Attention:{'已加载' if bilstm else '缺失'}")

    # 结构化
    comparison = {
        'baseline_summary': _baseline_summary(baseline),
        'text_cnn': cnn,
        'text_bilstm': bilstm,
    }
    json_path = os.path.join(STATS_DIR, 'deep_learning_comparison.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(comparison, f, ensure_ascii=False, indent=2)
    print(f"\n  JSON -> {json_path}")

    # Markdown
    md = generate_markdown(baseline, cnn, bilstm)
    md_path = os.path.join(STATS_DIR, 'deep_learning_comparison.md')
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md)
    print(f"  Markdown -> {md_path}")

    if args.open:
        print(f"\n报告路径: {md_path}")


if __name__ == '__main__':
    main()
