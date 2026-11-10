#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
多模态融合共享特征与分类器 (multimodal_features.py)
===================================================
训练脚本（scripts/train_fusion_model.py）与服务模块（risk_assessment.py、
Flask 多模态评估端点）共同依赖的特征提取与晚期融合分类器。

特征：
    text  — 12 维统计/关键词特征（不依赖 TF-IDF 词表，对新样本稳健）
    voice — 20 维 MFCC 均值（16kHz）
    image — 19 维颜色/噪声/边缘特征（与 train_image_baseline.basic 一致）

晚期融合策略（LateFusionClassifier.strategy）：
    stacking — 在三模态 P(fraud) 上学习 LogisticRegression 元分类器
    mean     — 三概率平均
    max      — 取最大概率
    weighted — 固定权重 0.30/0.35/0.35
    vote     — 0.5 阈值多数投票（3 模态不会平票）
"""

import os
import re

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin


# ============================================================
#  文本特征
# ============================================================

SCAM_KEYWORDS = [
    '中奖', '奖金', '转账', '验证码', '银行卡', '冻结', '解冻',
    '退税', '客服', '扫码', '领取', '幸运', '点击链接', '安全账户',
    '公安', '警察', '法院', '通缉', '洗钱', '征信', '年费', '赔偿',
    '快递丢失', '身份证',
]
URGENT_KEYWORDS = [
    '立即', '立刻', '马上', '紧急', '逾期', '否则', '限时', '名额有限',
]
MONEY_KEYWORDS = ['元', '万元', '奖金', '退款', '赔偿', '年费', '账户']
NORMAL_KEYWORDS = [
    '妈', '爸', '吃饭', '天气', '回家', '周末', '快递到了', '会议',
    '下班', '加班', '便利店', '跑', '带伞',
]

_URL_PATTERN = re.compile(r'https?://|www\.|[a-z0-9-]+\.(cn|com|net|ly)/',
                          re.IGNORECASE)
_PHONE_PATTERN = re.compile(r'1[3-9]\d{9}|0\d{2,3}-?\d{7,8}')
_PUNCT_PATTERN = re.compile(r'[，。！？、；：,.!?;:~…]')


def extract_text_features(text):
    """提取 12 维文本特征

    [长度, 数字比例, 诈骗词数, URL标志, 电话标志, 感叹号数, 问号数,
     标点密度, 正常词数, 金额词数, 紧急词数, 诈骗词命中比]
    """
    text = str(text)
    length = len(text)
    digits = sum(c.isdigit() for c in text)
    digit_ratio = digits / length if length > 0 else 0.0

    scam_count = sum(1 for w in SCAM_KEYWORDS if w in text)
    urgent_count = sum(1 for w in URGENT_KEYWORDS if w in text)
    money_count = sum(1 for w in MONEY_KEYWORDS if w in text)
    normal_count = sum(1 for w in NORMAL_KEYWORDS if w in text)

    has_url = 1 if _URL_PATTERN.search(text) else 0
    has_phone = 1 if _PHONE_PATTERN.search(text) else 0

    excl = text.count('!') + text.count('！')
    qmark = text.count('?') + text.count('？')
    puncts = _PUNCT_PATTERN.findall(text)
    punct_density = len(puncts) / length if length > 0 else 0.0

    # 诈骗词 / (诈骗词+正常词+1)，区分中性文本
    scam_ratio = scam_count / (scam_count + normal_count + 1)

    return [
        length / 200.0,          # 归一化长度
        digit_ratio,
        scam_count / 5.0,
        float(has_url),
        float(has_phone),
        excl / 3.0,
        qmark / 3.0,
        punct_density,
        normal_count / 3.0,
        money_count / 3.0,
        urgent_count / 3.0,
        scam_ratio,
    ]


# ============================================================
#  语音特征
# ============================================================

def extract_voice_features(file_path_or_y, sr=16000):
    """提取 20 维 MFCC 均值

    Args:
        file_path_or_y: wav 路径，或已加载的波形 np.ndarray
        sr: file 为波形时的采样率
    """
    import librosa

    if isinstance(file_path_or_y, str):
        y, _ = librosa.load(file_path_or_y, sr=16000)
    else:
        y = file_path_or_y
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20)
    return np.mean(mfcc, axis=1).tolist()


# ============================================================
#  图像特征（与 train_image_baseline.basic_features 完全一致）
# ============================================================

def extract_image_features(file_path_or_rgb):
    """提取 19 维基础特征

    Args:
        file_path_or_rgb: 图片路径，或 RGB uint8 np.ndarray
    """
    import cv2

    if isinstance(file_path_or_rgb, str):
        from PIL import Image
        img_rgb = np.array(Image.open(file_path_or_rgb).convert('RGB'))
    else:
        img_rgb = file_path_or_rgb

    img = img_rgb.astype(np.float64)
    gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)

    rgb_mean = [img[:, :, c].mean() for c in range(3)]
    rgb_std = [img[:, :, c].std() for c in range(3)]

    hsv = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2HSV).astype(np.float64)
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


# ============================================================
#  案例加载
# ============================================================

def load_cases(cases_dir):
    """加载对齐案例集

    Returns:
        dict: {case_id: {'label', 'text', 'voice', 'image'}}
    """
    import csv

    labels = {}
    csv_path = os.path.join(cases_dir, 'labels.csv')
    with open(csv_path, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            labels[row['case_id']] = int(row['label'])

    cases = {}
    for case_id, label in labels.items():
        case_dir = os.path.join(cases_dir, case_id)
        with open(os.path.join(case_dir, 'text.txt'), 'r',
                  encoding='utf-8') as f:
            text = f.read()
        cases[case_id] = {
            'label': label,
            'text': text,
            'voice_path': os.path.join(case_dir, 'voice.wav'),
            'image_path': os.path.join(case_dir, 'image.png'),
        }
    return cases


def build_feature_matrices(cases, case_ids=None):
    """为案例集构建三模态特征矩阵 + 标签 + 早期融合拼接矩阵

    Returns:
        Xt, Xv, Xi, Xearly, y
    """
    if case_ids is None:
        case_ids = sorted(cases.keys())

    Xt, Xv, Xi, y = [], [], [], []
    for cid in case_ids:
        c = cases[cid]
        Xt.append(extract_text_features(c['text']))
        Xv.append(extract_voice_features(c['voice_path']))
        Xi.append(extract_image_features(c['image_path']))
        y.append(c['label'])

    Xt = np.array(Xt)
    Xv = np.array(Xv)
    Xi = np.array(Xi)
    y = np.array(y)
    Xearly = np.concatenate([Xt, Xv, Xi], axis=1)
    return Xt, Xv, Xi, Xearly, y


# ============================================================
#  晚期融合分类器
# ============================================================

STRATEGIES = ('stacking', 'mean', 'max', 'weighted', 'vote')
FIXED_WEIGHTS = np.array([0.30, 0.35, 0.35])  # text, voice, image


def _make_modality_pipeline():
    """单模态标准 LR pipeline（scaler + 逻辑回归）"""
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression

    return Pipeline([
        ('scaler', StandardScaler()),
        ('clf', LogisticRegression(
            C=1.0, max_iter=1000, class_weight='balanced')),
    ])


class LateFusionClassifier(BaseEstimator, ClassifierMixin):
    """晚期融合分类器

    fit 时训练文本/语音/图像三个模态 LR；预测时得三模态 P(fraud)，
    按 strategy 融合。整个对象可被 sklearn cross_val_score 直接驱动，
    CV 中每折整体重训，融合结果无信息泄漏。

    Args:
        strategy: stacking / mean / max / weighted / vote
    """

    def __init__(self, strategy='stacking'):
        if strategy not in STRATEGIES:
            raise ValueError(
                f"Unknown strategy: {strategy}, choose from {STRATEGIES}")
        self.strategy = strategy

    def fit(self, X, y):
        """X: dict {'text': Xt, 'voice': Xv, 'image': Xi}"""
        self.classes_ = np.array([0, 1])
        self.modalities_ = {}
        proba_matrix = np.zeros((len(y), 3))

        for j, key in enumerate(('text', 'voice', 'image')):
            pipe = _make_modality_pipeline()
            pipe.fit(X[key], y)
            self.modalities_[key] = pipe
            proba_matrix[:, j] = self._positive_proba(pipe, X[key])

        self.proba_matrix_ = proba_matrix

        if self.strategy == 'stacking':
            from sklearn.linear_model import LogisticRegression
            self.meta_ = LogisticRegression(
                C=1.0, max_iter=1000, class_weight='balanced')
            self.meta_.fit(proba_matrix, y)

        return self

    @staticmethod
    def _positive_proba(pipe, X):
        """抽取 P(label=1)"""
        proba = pipe.predict_proba(X)
        classes = list(pipe.classes_)
        idx = classes.index(1) if 1 in classes else 1
        return proba[:, idx]

    def modality_proba(self, X):
        """返回 (n, 3) 三模态 P(fraud) 矩阵"""
        out = np.zeros((len(X['text']), 3))
        for j, key in enumerate(('text', 'voice', 'image')):
            out[:, j] = self._positive_proba(self.modalities_[key], X[key])
        return out

    def predict_proba(self, X):
        mp = self.modality_proba(X)
        fused = self._fuse(mp)
        return np.column_stack([1 - fused, fused])

    def predict(self, X):
        proba = self.predict_proba(X)
        return (proba[:, 1] >= 0.5).astype(int)

    def predict_components(self, X):
        """融合 + 各模态分量（供接口展示）

        Returns:
            (fused_p1_array, dict modality -> P(fraud))
        """
        mp = self.modality_proba(X)
        return self._fuse(mp), {
            'text': mp[:, 0], 'voice': mp[:, 1], 'image': mp[:, 2]}

    def _fuse(self, mp):
        """按策略将 (n,3) 模态概率融合为 (n,) P(fraud)"""
        if self.strategy == 'mean':
            return mp.mean(axis=1)
        elif self.strategy == 'max':
            return mp.max(axis=1)
        elif self.strategy == 'weighted':
            return mp @ FIXED_WEIGHTS
        elif self.strategy == 'vote':
            votes = (mp >= 0.5).sum(axis=1)
            # 3 票中 ≥2 判 1；保持概率软输出供参考
            soft = mp.mean(axis=1)
            return np.where(votes >= 2, np.maximum(soft, 0.5),
                            np.minimum(soft, 0.49))
        elif self.strategy == 'stacking':
            return self.meta_.predict_proba(mp)[:, 1]
        raise ValueError(self.strategy)

    # --- 基于单条样本（非矩阵 dict）的便捷推理，供 Flask 服务使用 ---

    def predict_one_components(self, text_content, voice_path, image_path):
        """对单案例原始输入做融合推理

        Returns:
            dict: fused_proba, per-modality proba, per-modality score 0-100
        """
        xt = np.array([extract_text_features(text_content)])
        xv = np.array([extract_voice_features(voice_path)])
        xi = np.array([extract_image_features(image_path)])
        X = {'text': xt, 'voice': xv, 'image': xi}

        fused, comps = self.predict_components(X)
        return {
            'fused_proba': float(fused[0]),
            'modality_proba': {k: float(v[0]) for k, v in comps.items()},
            'modality_score': {
                k: int(round(float(v[0]) * 100)) for k, v in comps.items()},
        }
