#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
深度学习文本模型共享模块（TextCNN / BiLSTM 通用）

提供：
- 字符级词表构建与序列编码（中文友好，无需分词）
- PyTorch Dataset / DataLoader
- 训练循环（含早停）
- 评估指标计算（acc / precision / recall / F1 + 混淆矩阵）
- 模型与词表的保存/加载

被 train_text_cnn.py 与 train_text_bilstm.py 复用
"""
import os
import json
import re
import csv
import random
from typing import List, Tuple, Dict, Optional

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report
)

# 路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AI_SERVICE_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(AI_SERVICE_DIR, 'data')
PROCESSED_DIR = os.path.join(DATA_DIR, 'text', 'processed')
STATS_DIR = os.path.join(DATA_DIR, 'text', 'stats')
MODEL_DIR = os.path.join(AI_SERVICE_DIR, 'models')

# 词表特殊 token
PAD_TOKEN = '<pad>'
UNK_TOKEN = '<unk>'

# 全局配置（默认值，可被训练脚本覆盖）
DEFAULT_MAX_LEN = 128
DEFAULT_MIN_FREQ = 1
DEFAULT_VOCAB_MAX = 5000
SEED = 42


def set_seed(seed: int = SEED) -> None:
    """固定随机种子，保证可复现"""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


# ============================================================
# 数据加载
# ============================================================

def load_processed_data() -> Tuple[List[Tuple[str, int]], List[Tuple[str, int]], List[Tuple[str, int]]]:
    """
    加载 prepare_dataset.py 产出的 {train,val,test}.csv
    （表头 content,label,category；兼容旧格式的 text 列）
    返回：[(text, label), ...] 三元组
    """
    def _read(name: str) -> List[Tuple[str, int]]:
        path = os.path.join(PROCESSED_DIR, name)
        if not os.path.exists(path):
            raise FileNotFoundError(f"未找到 {path}，请先运行 prepare_dataset.py")
        out = []
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for r in reader:
                text = (r.get('content') or r.get('text') or '').strip()
                if not text:
                    continue
                label = int(r['label'])
                out.append((text, label))
        return out

    train = _read('train.csv')
    val = _read('val.csv')
    test = _read('test.csv')
    print(f"  数据加载: train={len(train)} val={len(val)} test={len(test)}")
    return train, val, test


# ============================================================
# 字符级词表
# ============================================================

def tokenize_chars(text: str) -> List[str]:
    """字符级分词：保留中文/英文/数字，去除多余空白"""
    text = re.sub(r'\s+', '', text)
    return list(text)


def build_vocab(texts: List[str], min_freq: int = DEFAULT_MIN_FREQ,
                vocab_max: int = DEFAULT_VOCAB_MAX) -> Dict[str, int]:
    """
    从训练文本构建字符级词表
    返回 token -> id 字典（含 <pad>=0, <unk>=1）
    """
    from collections import Counter
    counter = Counter()
    for t in texts:
        counter.update(tokenize_chars(t))

    # 按频率排序，过滤低频
    items = [(tok, cnt) for tok, cnt in counter.most_common() if cnt >= min_freq]
    items = items[:vocab_max - 2]  # 留两个位置给 pad/unk

    vocab = {PAD_TOKEN: 0, UNK_TOKEN: 1}
    for tok, _ in items:
        vocab[tok] = len(vocab)

    print(f"  词表大小: {len(vocab)}（训练集字符 {sum(counter.values())} 个）")
    return vocab


def encode_text(text: str, vocab: Dict[str, int], max_len: int = DEFAULT_MAX_LEN) -> List[int]:
    """字符级编码：text -> id 序列（截断/补齐到 max_len）"""
    ids = [vocab.get(c, vocab[UNK_TOKEN]) for c in tokenize_chars(text)]
    if len(ids) >= max_len:
        return ids[:max_len]
    return ids + [vocab[PAD_TOKEN]] * (max_len - len(ids))


# ============================================================
# Dataset / DataLoader
# ============================================================

class TextDataset(Dataset):
    """PyTorch 文本数据集"""

    def __init__(self, samples: List[Tuple[str, int]], vocab: Dict[str, int],
                 max_len: int = DEFAULT_MAX_LEN):
        self.samples = samples
        self.vocab = vocab
        self.max_len = max_len

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        text, label = self.samples[idx]
        ids = encode_text(text, self.vocab, self.max_len)
        return torch.tensor(ids, dtype=torch.long), torch.tensor(label, dtype=torch.long)


def make_dataloader(samples, vocab, batch_size=32, max_len=DEFAULT_MAX_LEN,
                    shuffle=True) -> DataLoader:
    """构造 DataLoader"""
    ds = TextDataset(samples, vocab, max_len)
    return DataLoader(ds, batch_size=batch_size, shuffle=shuffle, drop_last=False)


# ============================================================
# 训练与评估
# ============================================================

def train_model(model: nn.Module, train_loader: DataLoader, val_loader: DataLoader,
                epochs: int = 20, lr: float = 1e-3,
                device: str = 'cpu', verbose: bool = True) -> Tuple[nn.Module, Dict]:
    """
    训练循环（含早停）
    返回 (最佳模型, 训练历史)
    """
    model = model.to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-5)
    criterion = nn.CrossEntropyLoss()

    best_val_f1 = -1.0
    best_state = None
    patience, no_improve = 5, 0
    history = {'train_loss': [], 'val_loss': [], 'val_f1': [], 'val_acc': []}

    for epoch in range(1, epochs + 1):
        # 训练
        model.train()
        total_loss, total = 0.0, 0
        for x, y in train_loader:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad()
            logits = model(x)
            loss = criterion(logits, y)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * len(y)
            total += len(y)
        train_loss = total_loss / max(total, 1)

        # 验证
        val_loss, val_metrics = evaluate_loss_metrics(model, val_loader, criterion, device)
        history['train_loss'].append(train_loss)
        history['val_loss'].append(val_loss)
        history['val_f1'].append(val_metrics['f1'])
        history['val_acc'].append(val_metrics['acc'])

        if verbose:
            print(f"  Epoch {epoch:3d}/{epochs}: train_loss={train_loss:.4f} "
                  f"val_loss={val_loss:.4f} val_acc={val_metrics['acc']:.4f} "
                  f"val_f1={val_metrics['f1']:.4f}")

        # 早停
        if val_metrics['f1'] > best_val_f1:
            best_val_f1 = val_metrics['f1']
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            no_improve = 0
        else:
            no_improve += 1
            if no_improve >= patience:
                if verbose:
                    print(f"  早停：{patience} 个 epoch 无提升")
                break

    if best_state is not None:
        model.load_state_dict(best_state)
    return model, history


def evaluate_loss_metrics(model: nn.Module, loader: DataLoader,
                          criterion: nn.Module, device: str = 'cpu') -> Tuple[float, Dict]:
    """在给定 loader 上计算 loss + 指标"""
    model.eval()
    total_loss, total = 0.0, 0
    y_true, y_pred = [], []
    with torch.no_grad():
        for x, y in loader:
            x, y = x.to(device), y.to(device)
            logits = model(x)
            loss = criterion(logits, y)
            total_loss += loss.item() * len(y)
            total += len(y)
            pred = logits.argmax(dim=1)
            y_true.extend(y.cpu().tolist())
            y_pred.extend(pred.cpu().tolist())
    metrics = compute_metrics(y_true, y_pred)
    return total_loss / max(total, 1), metrics


def compute_metrics(y_true: List[int], y_pred: List[int]) -> Dict:
    """计算 acc / precision / recall / F1（weighted） + 混淆矩阵"""
    labels = sorted(set(y_true) | set(y_pred))
    cm = confusion_matrix(y_true, y_pred, labels=labels).tolist()
    report = classification_report(y_true, y_pred, output_dict=True, zero_division=0)
    return {
        'acc': float(accuracy_score(y_true, y_pred)),
        'precision': float(precision_score(y_true, y_pred, average='weighted', zero_division=0)),
        'recall': float(recall_score(y_true, y_pred, average='weighted', zero_division=0)),
        'f1': float(f1_score(y_true, y_pred, average='weighted', zero_division=0)),
        'confusion_matrix': cm,
        'labels': labels,
        'report': report,
    }


def predict_proba(model: nn.Module, texts: List[str], vocab: Dict[str, int],
                  max_len: int = DEFAULT_MAX_LEN, device: str = 'cpu') -> np.ndarray:
    """批量推理，返回每条文本的诈骗概率（label=1）"""
    model.eval()
    probs = []
    with torch.no_grad():
        for t in texts:
            ids = torch.tensor([encode_text(t, vocab, max_len)], dtype=torch.long).to(device)
            logits = model(ids)
            p = torch.softmax(logits, dim=1)
            probs.append(float(p[0][1].cpu()))
    return np.array(probs)


# ============================================================
# 保存 / 加载
# ============================================================

def save_model(model: nn.Module, vocab: Dict[str, int], model_name: str,
               config: Dict, metrics: Dict, history: Dict) -> None:
    """
    保存深度模型：3 个文件
    - models/<name>.pt         (模型权重)
    - models/<name>_vocab.json  (词表)
    - models/<name>_meta.json   (配置 + 指标 + 训练历史)
    """
    os.makedirs(MODEL_DIR, exist_ok=True)

    # 权重
    weight_path = os.path.join(MODEL_DIR, f"{model_name}.pt")
    torch.save(model.state_dict(), weight_path)

    # 词表
    vocab_path = os.path.join(MODEL_DIR, f"{model_name}_vocab.json")
    with open(vocab_path, 'w', encoding='utf-8') as f:
        json.dump(vocab, f, ensure_ascii=False, indent=2)

    # 元数据
    meta = {
        'model_name': model_name,
        'config': config,
        'metrics': metrics,
        'history': history,
    }
    meta_path = os.path.join(MODEL_DIR, f"{model_name}_meta.json")
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"  保存模型:")
    print(f"    权重 -> {weight_path}")
    print(f"    词表 -> {vocab_path}")
    print(f"    元数据 -> {meta_path}")


def load_vocab(model_name: str) -> Dict[str, int]:
    """加载模型配套词表"""
    path = os.path.join(MODEL_DIR, f"{model_name}_vocab.json")
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_meta(model_name: str) -> Dict:
    """加载模型元数据"""
    path = os.path.join(MODEL_DIR, f"{model_name}_meta.json")
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)
