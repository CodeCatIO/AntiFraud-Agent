#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TextCNN 文本诈骗检测深度学习模型（任务4 第一部分）

模型结构：
  Input (char ids, B×T)
    -> Embedding (B×T×D)
    -> 多尺度 Conv1d (kernels=[2,3,4,5]，各 num_filters 个)
    -> 各支路 max-over-time pooling
    -> 拼接 -> Dropout -> Linear(num_classes)

特征：字符级（中文友好，无需分词）
比较对象：train_text_baseline.py 的 12 组传统 ML ablation

输入：data/text/processed/{train,val,test}.csv
输出：
  - models/text_cnn.pt + text_cnn_vocab.json + text_cnn_meta.json
  - data/text/stats/text_cnn_results.json

用法：
  python train_text_cnn.py                  # 默认配置
  python train_text_cnn.py --epochs 50     # 调大 epoch
  python train_text_cnn.py --embed 256 --filters 128  # 调结构
"""
import os
import argparse
import torch
import torch.nn as nn
import torch.nn.functional as F

from deep_text_common import (
    set_seed, load_processed_data, build_vocab, make_dataloader,
    train_model, evaluate_loss_metrics, compute_metrics,
    save_model, DEFAULT_MAX_LEN,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATS_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), 'data', 'text', 'stats')


class TextCNN(nn.Module):
    """多尺度卷积 + max-pool 的 TextCNN（Kim 2014 风格）"""

    def __init__(self, vocab_size: int, embed_dim: int = 128,
                 num_filters: int = 64, kernel_sizes=(2, 3, 4, 5),
                 num_classes: int = 2, dropout: float = 0.5,
                 pad_idx: int = 0):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=pad_idx)
        # 多尺度一维卷积分支
        self.convs = nn.ModuleList([
            nn.Conv1d(in_channels=embed_dim, out_channels=num_filters,
                      kernel_size=k, padding=(k - 1) // 2)
            for k in kernel_sizes
        ])
        self.dropout = nn.Dropout(dropout)
        # 输入维度 = num_filters × len(kernel_sizes)
        self.fc = nn.Linear(num_filters * len(kernel_sizes), num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, T) -> (B, T, D) -> (B, D, T) 供 Conv1d
        emb = self.embedding(x).transpose(1, 2)
        # 各卷积分支 + ReLU + max-over-time pooling
        branch_outs = []
        for conv in self.convs:
            c = F.relu(conv(emb))               # (B, F, T')
            pooled = F.adaptive_max_pool1d(c, 1).squeeze(-1)  # (B, F)
            branch_outs.append(pooled)
        cat = torch.cat(branch_outs, dim=1)    # (B, F*K)
        cat = self.dropout(cat)
        return self.fc(cat)


def main():
    parser = argparse.ArgumentParser(description='TextCNN 文本深度学习训练')
    parser.add_argument('--epochs', type=int, default=30)
    parser.add_argument('--batch_size', type=int, default=32)
    parser.add_argument('--lr', type=float, default=1e-3)
    parser.add_argument('--embed', type=int, default=128, help='embedding dim')
    parser.add_argument('--filters', type=int, default=64, help='每个 kernel size 的 filter 数')
    parser.add_argument('--kernels', type=int, nargs='+', default=[2, 3, 4, 5])
    parser.add_argument('--dropout', type=float, default=0.5)
    parser.add_argument('--max_len', type=int, default=DEFAULT_MAX_LEN)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()

    set_seed(args.seed)
    device = 'cuda' if torch.cuda.is_available() else 'cpu'

    print("=" * 60)
    print("TextCNN 文本深度学习训练")
    print("=" * 60)
    print(f"  device: {device}")
    print(f"  超参数: epochs={args.epochs} batch={args.batch_size} lr={args.lr}")
    print(f"  模型: embed_dim={args.embed} filters={args.filters} "
          f"kernels={args.kernels} dropout={args.dropout} max_len={args.max_len}")

    # 1) 数据
    print("\n[1/4] 加载数据...")
    train, val, test = load_processed_data()

    # 2) 词表
    print("\n[2/4] 构建字符级词表...")
    vocab = build_vocab([t for t, _ in train])

    # 3) 模型与训练
    print("\n[3/4] 构造 TextCNN + 训练...")
    model = TextCNN(
        vocab_size=len(vocab),
        embed_dim=args.embed,
        num_filters=args.filters,
        kernel_sizes=tuple(args.kernels),
        num_classes=2,
        dropout=args.dropout,
        pad_idx=vocab['<pad>'],
    )
    print(f"  参数量: {sum(p.numel() for p in model.parameters()):,}")

    train_loader = make_dataloader(train, vocab, args.batch_size, args.max_len, shuffle=True)
    val_loader = make_dataloader(val, vocab, args.batch_size, args.max_len, shuffle=False)

    model, history = train_model(
        model, train_loader, val_loader,
        epochs=args.epochs, lr=args.lr, device=device, verbose=True
    )

    # 4) 测试集评估 + 保存
    print("\n[4/4] 测试集评估 + 保存...")
    test_loader = make_dataloader(test, vocab, args.batch_size, args.max_len, shuffle=False)
    criterion = nn.CrossEntropyLoss()
    test_loss, test_metrics = evaluate_loss_metrics(model, test_loader, criterion, device)
    print(f"  测试集: loss={test_loss:.4f} acc={test_metrics['acc']:.4f} "
          f"precision={test_metrics['precision']:.4f} recall={test_metrics['recall']:.4f} "
          f"f1={test_metrics['f1']:.4f}")
    print(f"  混淆矩阵 (labels={test_metrics['labels']}):")
    for row in test_metrics['confusion_matrix']:
        print(f"    {row}")

    # 保存模型
    config = {
        'model_type': 'TextCNN',
        'vocab_size': len(vocab),
        'embed_dim': args.embed,
        'num_filters': args.filters,
        'kernel_sizes': args.kernels,
        'dropout': args.dropout,
        'max_len': args.max_len,
        'seed': args.seed,
        'epochs_run': len(history['train_loss']),
    }
    save_model(model, vocab, 'text_cnn', config,
               {'test': test_metrics}, history)

    # 保存指标到 stats 目录（供对比报告使用）
    os.makedirs(STATS_DIR, exist_ok=True)
    results_path = os.path.join(STATS_DIR, 'text_cnn_results.json')
    with open(results_path, 'w', encoding='utf-8') as f:
        import json
        json.dump({
            'model': 'TextCNN',
            'config': config,
            'test_metrics': test_metrics,
            'best_val_f1': max(history['val_f1']) if history['val_f1'] else 0,
            'history': history,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n  结果 -> {results_path}")
    print("\nTextCNN 训练完成。")


if __name__ == '__main__':
    main()
