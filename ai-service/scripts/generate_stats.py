#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据集统计报告生成器

汇总文本/语音/图像三个模态的统计数据，生成 JSON + Markdown 报告。

输入：data/{text,voice,image}/stats/stats.json
输出：data/stats_report.json + data/stats_report.md
"""
import os
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AI_SERVICE_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(AI_SERVICE_DIR, 'data')


def load_stats(modality):
    """加载单个模态的统计"""
    stats_path = os.path.join(DATA_DIR, modality, 'stats', 'stats.json')
    if not os.path.exists(stats_path):
        return None
    with open(stats_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def generate_markdown(report):
    """生成 Markdown 报告"""
    lines = ["# 数据集统计报告\n"]

    # 文本
    if report.get('text'):
        s = report['text']
        lines.append("## 文本数据集\n")
        lines.append(f"- 总样本数: {s.get('total_samples', 'N/A')}")
        lines.append(f"- 诈骗样本: {s.get('fraud_samples', 'N/A')}")
        lines.append(f"- 正常样本: {s.get('normal_samples', 'N/A')}")
        lines.append(f"- 诈骗比例: {s.get('fraud_ratio', 'N/A')}")
        lines.append(f"- 平均字符长度: {s.get('avg_char_length', 'N/A')}")
        lines.append(f"- 平均词数: {s.get('avg_token_length', 'N/A')}")
        split = s.get('split', {})
        lines.append(
            f"- 数据集划分: 训练 {split.get('train', 'N/A')} / "
            f"验证 {split.get('val', 'N/A')} / 测试 {split.get('test', 'N/A')}"
        )

        top_words = s.get('top10_fraud_words', [])
        if top_words:
            lines.append("\n### 诈骗样本词频 Top10\n")
            lines.append("| 词语 | 出现次数 |")
            lines.append("|------|---------|")
            for word, count in top_words:
                lines.append(f"| {word} | {count} |")

        examples = s.get('examples', {})
        if examples:
            lines.append("\n### 示例样本\n")
            fraud_examples = examples.get('fraud', [])
            if fraud_examples:
                lines.append("**诈骗样本：**")
                for ex in fraud_examples:
                    lines.append(f"- {ex}")
            normal_examples = examples.get('normal', [])
            if normal_examples:
                lines.append("\n**正常样本：**")
                for ex in normal_examples:
                    lines.append(f"- {ex}")
        lines.append("")

    # 语音
    if report.get('voice'):
        s = report['voice']
        lines.append("## 语音数据集\n")
        lines.append(f"- 总样本数: {s.get('total_samples', 'N/A')}")
        lines.append(f"- 增强样本数: {s.get('augmented_samples', 'N/A')}")
        lines.append(f"- 含增强总样本: {s.get('total_with_augmentation', 'N/A')}")
        lines.append(f"- 诈骗样本: {s.get('fraud_samples', 'N/A')}")
        lines.append(f"- 正常样本: {s.get('normal_samples', 'N/A')}")
        lines.append(
            f"- 总时长: {s.get('total_duration_sec', 'N/A')} 秒 "
            f"({s.get('total_duration_hours', 'N/A')} 小时)"
        )
        lines.append(f"- 目标采样率: {s.get('target_sample_rate', 'N/A')} Hz")
        lines.append(f"- MFCC维度: {s.get('mfcc_dimensions', 'N/A')}")
        lines.append(f"- 数据增强方式: {', '.join(s.get('augmentation_types', []))}")
        lines.append("")

    # 图像
    if report.get('image'):
        s = report['image']
        lines.append("## 图像数据集\n")
        lines.append(f"- 总样本数: {s.get('total_samples', 'N/A')}")
        lines.append(f"- 增强样本数: {s.get('augmented_samples', 'N/A')}")
        lines.append(f"- 含增强总样本: {s.get('total_with_augmentation', 'N/A')}")
        lines.append(f"- 诈骗样本: {s.get('fraud_samples', 'N/A')}")
        lines.append(f"- 正常样本: {s.get('normal_samples', 'N/A')}")
        lines.append(f"- 篡改样本: {s.get('tampered_samples', 'N/A')}")
        lines.append(f"- 目标尺寸: {s.get('target_size', 'N/A')}")
        lines.append(f"- 原始尺寸: {', '.join(s.get('original_sizes', []))}")
        lines.append(f"- 已归一化: {s.get('normalized', 'N/A')}")
        lines.append(f"- 数据增强方式: {', '.join(s.get('augmentation_types', []))}")
        lines.append("")

    lines.append("---")
    lines.append("\n> 本报告由 `generate_stats.py` 自动生成。")

    return '\n'.join(lines)


def main():
    print("=" * 60)
    print("数据集统计报告生成")
    print("=" * 60)

    report = {}

    # 加载各模态统计
    for modality in ['text', 'voice', 'image']:
        print(f"\n[{modality}] 加载统计...")
        stats = load_stats(modality)
        if stats:
            report[modality] = stats
            print(f"  已加载")
        else:
            print(f"  未找到统计文件，请先运行 preprocess_{modality}.py")

    # 保存 JSON
    json_path = os.path.join(DATA_DIR, 'stats_report.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n保存 JSON -> {json_path}")

    # 保存 Markdown
    md_path = os.path.join(DATA_DIR, 'stats_report.md')
    md_content = generate_markdown(report)
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    print(f"保存 Markdown -> {md_path}")

    print(f"\n统计报告生成完成。")


if __name__ == '__main__':
    main()
