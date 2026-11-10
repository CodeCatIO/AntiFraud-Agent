#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
BiLSTM + Attention 文本诈骗检测深度学习模型（任务4 第二部分）

模型结构：
  Input (char ids, B×T)
    -> Embedding (B×T×D)
    -> BiLSTM (2 层，双向) -> 输出 (B×T×2H)
    -> Self-Attention 加权求和 -> (B×2H)
    -> Dropout -> Linear -> num_classes

特征：字符级（中文友好，无需分词）
对比对象：train_text_baseline.py 的 12 组传统 ML + train_text_cnn.py 的 TextCNN

输入：data/text/processed/{train,val,test}.csv
输出：
  - models/text_bilstm.pt + text_bilstm_vocab.json + text_bilstm_meta.json
  - data/text/stats/text_bilstm_results.json

用法：
  python train_text_bilstm.py
  python train_text_bilstm.py --epochs 50 --hidden 256
"""
import os
import json
import time
import argparse
import torch
import torch.nn as nn
import torch.nn.functional as F
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

from deep_text_common import (
    set_seed, load_processed_data, build_vocab, make_dataloader,
    train_model, evaluate_loss_metrics,
    save_model, DEFAULT_MAX_LEN,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AI_SERVICE_DIR = os.path.dirname(SCRIPT_DIR)
STATS_DIR = os.path.join(AI_SERVICE_DIR, 'data', 'text', 'stats')
REPORTS_DIR = os.path.join(AI_SERVICE_DIR, 'reports')


def plot_confusion_matrix(cm, title, save_path):
    fig, ax = plt.subplots(figsize=(5, 4))
    im = ax.imshow(cm, interpolation='nearest', cmap=plt.cm.Blues)
    ax.set_title(title)
    fig.colorbar(im)
    classes = ['正常', '诈骗']
    ax.set_xticks([0, 1]); ax.set_yticks([0, 1])
    ax.set_xticklabels(classes); ax.set_yticklabels(classes)
    ax.set_xlabel('Predicted'); ax.set_ylabel('True')
    thresh = cm.max() / 2 if cm.max() > 0 else 0.5
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, format(int(cm[i, j]), 'd'), ha='center', va='center',
                    color='white' if cm[i, j] > thresh else 'black')
    fig.tight_layout()
    fig.savefig(save_path, dpi=120)
    plt.close(fig)


class SelfAttention(nn.Module):
    """对 BiLSTM 输出做自注意力加权（Bahdanau 风格的简化版）"""

    def __init__(self, hidden_dim: int, attn_dim: int = 64):
        super().__init__()
        self.attn = nn.Sequential(
            nn.Linear(hidden_dim, attn_dim),
            nn.Tanh(),
            nn.Linear(attn_dim, 1, bias=False),
        )

    def forward(self, lstm_out: torch.Tensor, mask: torch.Tensor = None) -> torch.Tensor:
        """
        lstm_out: (B, T, H)
        mask: (B, T) 0/1（1 表示有效 token）
        return: (B, H) 加权聚合
        """
        scores = self.attn(lstm_out).squeeze(-1)  # (B, T)
        if mask is not None:
            scores = scores.masked_fill(mask == 0, -1e9)
        weights = F.softmax(scores, dim=1).unsqueeze(-1)  # (B, T, 1)
        return (lstm_out * weights).sum(dim=1)  # (B, H)


class BiLSTMAttn(nn.Module):
    """BiLSTM + Self-Attention 文本分类模型"""

    def __init__(self, vocab_size: int, embed_dim: int = 128,
                 hidden_dim: int = 128, num_layers: int = 2,
                 num_classes: int = 2, dropout: float = 0.5,
                 pad_idx: int = 0, attn_dim: int = 64):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=pad_idx)
        self.lstm = nn.LSTM(
            input_size=embed_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=True,
            dropout=dropout if num_layers > 1 else 0,
        )
        # 注意力作用于 2×hidden_dim（双向拼接）
        self.attn = SelfAttention(hidden_dim * 2, attn_dim)
        self.dropout = nn.Dropout(dropout)
        # 输入维度 = 2×hidden_dim
        self.fc = nn.Linear(hidden_dim * 2, num_classes)
        self.pad_idx = pad_idx

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, T)
        emb = self.embedding(x)  # (B, T, D)
        out, _ = self.lstm(emb)  # (B, T, 2H)
        # mask: 非pad位置=1
        mask = (x != self.pad_idx).long()
        attended = self.attn(out, mask)  # (B, 2H)
        attended = self.dropout(attended)
        return self.fc(attended)


def main():
    parser = argparse.ArgumentParser(description='BiLSTM+Attention 文本深度学习训练')
    parser.add_argument('--epochs', type=int, default=30)
    parser.add_argument('--batch_size', type=int, default=32)
    parser.add_argument('--lr', type=float, default=1e-3)
    parser.add_argument('--embed', type=int, default=128)
    parser.add_argument('--hidden', type=int, default=128)
    parser.add_argument('--layers', type=int, default=2)
    parser.add_argument('--dropout', type=float, default=0.5)
    parser.add_argument('--max_len', type=int, default=DEFAULT_MAX_LEN)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()

    set_seed(args.seed)
    t_start = time.time()
    device = 'cuda' if torch.cuda.is_available() else 'cpu'

    print("=" * 60)
    print("BiLSTM + Attention 文本深度学习训练")
    print("=" * 60)
    print(f"  device: {device}")
    print(f"  超参数: epochs={args.epochs} batch={args.batch_size} lr={args.lr}")
    print(f"  模型: embed_dim={args.embed} hidden={args.hidden} "
          f"layers={args.layers} dropout={args.dropout} max_len={args.max_len}")

    # 1) 数据
    print("\n[1/4] 加载数据...")
    train, val, test = load_processed_data()

    # 2) 词表
    print("\n[2/4] 构建字符级词表...")
    vocab = build_vocab([t for t, _ in train])

    # 3) 模型与训练
    print("\n[3/4] 构造 BiLSTM+Attn + 训练...")
    model = BiLSTMAttn(
        vocab_size=len(vocab),
        embed_dim=args.embed,
        hidden_dim=args.hidden,
        num_layers=args.layers,
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

    # 保存
    config = {
        'model_type': 'BiLSTMAttn',
        'vocab_size': len(vocab),
        'embed_dim': args.embed,
        'hidden_dim': args.hidden,
        'num_layers': args.layers,
        'dropout': args.dropout,
        'max_len': args.max_len,
        'seed': args.seed,
        'epochs_run': len(history['train_loss']),
    }
    save_model(model, vocab, 'text_bilstm', config,
               {'test': test_metrics}, history)

    os.makedirs(STATS_DIR, exist_ok=True)
    results_path = os.path.join(STATS_DIR, 'text_bilstm_results.json')
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump({
            'model': 'BiLSTMAttn',
            'config': config,
            'test_metrics': test_metrics,
            'best_val_f1': max(history['val_f1']) if history['val_f1'] else 0,
            'history': history,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n  结果 -> {results_path}")

    # 任务5要求：逐类指标 JSON + reports/ 混淆矩阵
    elapsed_sec = round(time.time() - t_start, 1)
    rep = test_metrics.get('report', {})
    import numpy as _np
    bilstm_metrics = {
        'model': 'BiLSTM+Attention',
        'training_seconds': elapsed_sec,
        'epochs_run': len(history['train_loss']),
        'best_val_f1': round(max(history['val_f1']), 4) if history['val_f1'] else 0,
        'accuracy': round(test_metrics['acc'], 4),
        'per_class': {
            '0_正常': {k: (round(float(rep['0'][k]), 4) if k != 'support' else int(rep['0'][k]))
                      for k in ('precision', 'recall', 'f1-score', 'support')},
            '1_诈骗': {k: (round(float(rep['1'][k]), 4) if k != 'support' else int(rep['1'][k]))
                      for k in ('precision', 'recall', 'f1-score', 'support')},
        },
        'confusion_matrix': test_metrics['confusion_matrix'],
        'hyperparams': {
            'epochs_max': args.epochs, 'batch_size': args.batch_size,
            'lr': args.lr, 'embed_dim': args.embed, 'hidden_dim': args.hidden,
            'num_layers': args.layers, 'dropout': args.dropout,
            'max_len': args.max_len, 'seed': args.seed,
            'optimizer': 'Adam', 'loss': 'CrossEntropyLoss',
            'early_stopping_patience': 5,
        },
        'param_count': sum(p.numel() for p in model.parameters()),
    }
    os.makedirs(REPORTS_DIR, exist_ok=True)
    with open(os.path.join(REPORTS_DIR, 'bilstm_metrics.json'), 'w',
              encoding='utf-8') as f:
        json.dump(bilstm_metrics, f, ensure_ascii=False, indent=2)
    cm = _np.array(test_metrics['confusion_matrix'])
    plot_confusion_matrix(cm, 'BiLSTM+Attention (test)',
                          os.path.join(REPORTS_DIR, 'confusion_matrix_bilstm.png'))
    print(f"  逐类指标/混淆矩阵 -> {REPORTS_DIR}  (耗时 {elapsed_sec}s)")
    print("\nBiLSTM+Attention 训练完成。")


if __name__ == '__main__':
    main()
