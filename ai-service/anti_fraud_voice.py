#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
语音伪造检测模块 (anti_fraud_voice.py)
=====================================
用途：对音频文件进行AI合成语音检测，提取声学特征判断是否为伪造语音

推理优先级：
    1) ML 模型预测（models/voice_baseline.joblib，MFCC+Δ 特征 + SVM）
    2) 启发式规则 fallback（MFCC 平滑度/频谱质心/零交叉率/节奏均匀性）
    3) 文件信息 fallback（降级模式）

调用方式：
    python anti_fraud_voice.py "音频文件路径"
输出：JSON格式到stdout，包含risk_score, risk_level, detail, features,
      以及 isFraud, confidence（仅 ML 路径）
依赖：librosa, numpy, scikit-learn, joblib
"""

import sys
import json
import os


_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_MODELS_DIR = os.path.join(_BASE_DIR, 'models')

# ============================================================
#  可选模型注册表（models/ 下的 joblib 文件）
# ============================================================
# 三个可在页面上切换对比的模型；default/baseline 指向 voice_baseline.joblib
# （train_voice_models.py 会把它写成三模型中测试集 F1 最高者）
VOICE_MODELS = {
    'gmm': 'voice_gmm.joblib',
    'svm': 'voice_svm.joblib',
    'rf': 'voice_rf.joblib',
    'random_forest': 'voice_rf.joblib',  # 别名
}
DEFAULT_MODEL_FILE = 'voice_baseline.joblib'

# 模型缓存：{model_name: bundle}，避免每次请求重新加载
_VOICE_BUNDLE_CACHE = {}


class VoiceModelNotFoundError(FileNotFoundError):
    """显式指定的语音模型权重不存在"""


def _resolve_model_file(model_name):
    """把请求里的模型名解析成 models/ 下的 joblib 文件名"""
    if model_name in (None, '', 'default', 'baseline'):
        return DEFAULT_MODEL_FILE
    key = str(model_name).lower()
    if key not in VOICE_MODELS:
        raise ValueError(
            f"未知语音模型: {model_name}，可选: {sorted(set(VOICE_MODELS))}")
    return VOICE_MODELS[key]


def _load_voice_bundle(model_name=None):
    """按模型名懒加载 bundle dict 并缓存。

    默认模型（voice_baseline.joblib）不存在时返回 None（走启发式降级）；
    显式指定的模型不存在时抛 VoiceModelNotFoundError（避免静默测错模型）。
    """
    cache_key = model_name or 'default'
    if cache_key in _VOICE_BUNDLE_CACHE:
        return _VOICE_BUNDLE_CACHE[cache_key]

    import joblib
    # GMM bundle 反序列化需要 scripts/gmm_classifier.py（GMMClassifier）
    _scripts_dir = os.path.join(_BASE_DIR, 'scripts')
    if _scripts_dir not in sys.path:
        sys.path.insert(0, _scripts_dir)
    fname = _resolve_model_file(model_name)
    path = os.path.join(_MODELS_DIR, fname)
    if not os.path.exists(path):
        if cache_key == 'default':
            _VOICE_BUNDLE_CACHE[cache_key] = None
            return None
        raise VoiceModelNotFoundError(
            f"语音模型 {model_name} 的权重文件不存在: {fname}，"
            f"请先运行 scripts/train_voice_models.py")
    bundle = joblib.load(path)
    _VOICE_BUNDLE_CACHE[cache_key] = bundle
    return bundle


def _get_voice_model():
    """懒加载默认模型 voice_baseline.joblib（保留旧调用兼容）"""
    return _load_voice_bundle(None)


def _extract_ml_features(file_path, n_mfcc=20, target_sr=16000):
    """提取与训练时一致的 delta MFCC 特征向量

    Returns:
        np.ndarray (1, 3*n_mfcc) 或 None（提取失败）
    """
    try:
        import librosa
        import numpy as np

        y, sr = librosa.load(file_path, sr=target_sr)
        if len(y) == 0:
            return None
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=n_mfcc)
        mean = np.mean(mfcc, axis=1)
        d1 = librosa.feature.delta(mfcc)
        d2 = librosa.feature.delta(mfcc, order=2)
        d1_mean = np.mean(d1, axis=1)
        d2_mean = np.mean(d2, axis=1)
        feat = np.concatenate([mean, d1_mean, d2_mean])
        return feat.reshape(1, -1)
    except Exception:
        return None


def _predict_with_ml(file_path, model_name=None):
    """使用指定 ML 模型预测，返回结果 dict 或 None

    model_name: None/default -> voice_baseline.joblib；
                也可传 gmm / svm / rf 选择对应模型。
    默认模型不存在时返回 None（走启发式降级）；显式指定的模型缺失时抛异常。

    输出字段：risk_score, risk_level, detail, isFraud, confidence,
              features, source='ml'
    """
    model = _load_voice_bundle(model_name)
    if model is None:
        return None

    n_mfcc = model.get('n_mfcc', 20)
    target_sr = model.get('target_sr', 16000)
    feat_kind = model.get('feature_kind', 'delta')
    pipeline = model.get('pipeline')
    model_key = model.get('model_name', model_name or 'voice_baseline')
    model_label = model.get('model_label',
                            {'gmm': 'GMM', 'svm': 'SVM', 'rf': '随机森林'}.get(
                                str(model_key), str(model_key)))

    if pipeline is None:
        return None

    # 根据训练时特征类型提取
    try:
        import librosa
        import numpy as np

        y, sr = librosa.load(file_path, sr=target_sr)
        if len(y) == 0:
            return None
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=n_mfcc)

        if feat_kind == 'mean':
            feat = np.mean(mfcc, axis=1)
        elif feat_kind == 'stats':
            feat = np.concatenate([np.mean(mfcc, axis=1),
                                   np.std(mfcc, axis=1)])
        elif feat_kind == 'delta':
            d1 = librosa.feature.delta(mfcc)
            d2 = librosa.feature.delta(mfcc, order=2)
            feat = np.concatenate([np.mean(mfcc, axis=1),
                                   np.mean(d1, axis=1),
                                   np.mean(d2, axis=1)])
        else:
            feat = np.mean(mfcc, axis=1)
        feat = feat.reshape(1, -1)
    except Exception:
        return None

    try:
        pred = int(pipeline.predict(feat)[0])
        proba = pipeline.predict_proba(feat)[0]
        # classes_ 顺序：[0, 1]，1=诈骗
        classes = getattr(pipeline, 'classes_', None)
        if classes is None and hasattr(pipeline, 'steps'):
            # Pipeline 没暴露 classes_，从最后一步取
            classes = pipeline.steps[-1][1].classes_
        if classes is None:
            classes = [0, 1]
        idx_fraud = list(classes).index(1) if 1 in list(classes) else 1
        fraud_proba = float(proba[idx_fraud]) if len(proba) > idx_fraud else 0.5
    except Exception:
        return None

    # 风险分：直接用诈骗概率 × 100
    risk_score = int(round(fraud_proba * 100))
    if risk_score < 30:
        risk_level = "低风险"
    elif risk_score < 70:
        risk_level = "中风险"
    else:
        risk_level = "高风险"

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "detail": f"ML模型预测（MFCC+ΔΔ 特征 + {model_label}），AI合成概率 "
                  f"{fraud_proba:.2%}",
        "isFraud": bool(pred == 1),
        "confidence": round(fraud_proba if pred == 1 else 1 - fraud_proba, 4),
        "fraudProbability": round(fraud_proba, 4),
        "model": model_key,
        "modelLabel": model_label,
        "features": {
            "feature_kind": feat_kind,
            "n_mfcc": n_mfcc,
            "model": model_key,
            "model_label": model_label,
        },
        "source": "ml",
    }


# ============================================================
#  启发式规则 fallback
# ============================================================

def analyze_voice_fallback(file_path):
    """
    librosa处理失败时的降级处理，返回基于文件信息的模拟结果

    Args:
        file_path: 音频文件路径

    Returns:
        dict: 模拟的检测结果
    """
    file_size = 0
    try:
        file_size = os.path.getsize(file_path)
    except Exception:
        pass

    # 基于文件大小做简单启发式判断
    if file_size == 0:
        risk_score = 0
        risk_level = "无风险"
        detail = "音频文件为空或无法读取"
    elif file_size < 10000:
        risk_score = 25
        risk_level = "低风险"
        detail = "音频片段过短，风险较低"
    else:
        risk_score = 40
        risk_level = "低风险"
        detail = "音频特征分析降级模式，建议人工复核"

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "detail": detail,
        "features": {
            "mfcc_mean": 0.0,
            "spectral_centroid": 0.0,
            "zero_crossing_rate": 0.0,
            "note": "降级模式，特征未提取"
        },
        "source": "fallback",
    }


def analyze_voice_heuristic(file_path):
    """启发式规则分析（原 analyze_voice 的逻辑，作为 ML 不可用时的 fallback）

    Args:
        file_path: 音频文件路径

    Returns:
        dict: 包含risk_score, risk_level, detail, features的字典
    """
    try:
        import librosa
        import numpy as np

        # 加载音频
        y, sr = librosa.load(file_path, sr=None)

        if len(y) == 0:
            return {
                "risk_score": 0,
                "risk_level": "无风险",
                "detail": "音频内容为空",
                "features": {}
            }

        # 提取MFCC特征（13维）
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        mfcc_mean = float(np.mean(mfcc))
        mfcc_std = float(np.std(mfcc))

        # 提取频谱质心
        spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
        spectral_centroid_mean = float(np.mean(spectral_centroid))

        # 提取零交叉率
        zero_crossing_rate = librosa.feature.zero_crossing_rate(y)
        zcr_mean = float(np.mean(zero_crossing_rate))

        # ===== 启发式规则判断AI合成 =====

        # 1. 频谱平滑度分析：AI合成语音的MFCC标准差通常较小（频谱更平滑）
        spectral_smoothness_score = 0
        if mfcc_std < 3.0:
            spectral_smoothness_score = 30  # 过于平滑，可疑
        elif mfcc_std < 5.0:
            spectral_smoothness_score = 15
        else:
            spectral_smoothness_score = 0

        # 2. 频谱质心分析：AI合成语音的频谱质心可能偏移
        centroid_score = 0
        if spectral_centroid_mean > 4000 or spectral_centroid_mean < 1000:
            centroid_score = 20  # 频谱质心异常
        elif spectral_centroid_mean > 3500 or spectral_centroid_mean < 1500:
            centroid_score = 10

        # 3. 零交叉率分析：AI合成语音的零交叉率可能过于均匀
        zcr_score = 0
        zcr_std = float(np.std(zero_crossing_rate))
        if zcr_std < 0.01:
            zcr_score = 25  # 零交叉率过于均匀，可疑
        elif zcr_std < 0.03:
            zcr_score = 10

        # 4. 语音节奏均匀性：分析能量包络的方差
        rms = librosa.feature.rms(y=y)
        rms_std = float(np.std(rms))
        rhythm_score = 0
        if rms_std < 0.01:
            rhythm_score = 20  # 节奏过于均匀
        elif rms_std < 0.03:
            rhythm_score = 10

        # 计算综合风险分
        risk_score = min(spectral_smoothness_score + centroid_score + zcr_score + rhythm_score, 100)

        # 确定风险等级
        if risk_score < 30:
            risk_level = "低风险"
            detail = "语音特征正常，未检测到明显AI合成痕迹（启发式规则）"
        elif risk_score < 70:
            risk_level = "中风险"
            if spectral_smoothness_score >= 30:
                detail = "语音频谱平滑度异常，疑似AI合成（启发式规则）"
            elif zcr_score >= 25:
                detail = "语音节奏过于均匀，疑似AI合成（启发式规则）"
            else:
                detail = "语音特征存在异常，建议人工复核（启发式规则）"
        else:
            risk_level = "高风险"
            detail = "语音频谱平滑度异常，疑似AI合成（启发式规则）"

        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "detail": detail,
            "features": {
                "mfcc_mean": round(mfcc_mean, 4),
                "mfcc_std": round(mfcc_std, 4),
                "spectral_centroid": round(spectral_centroid_mean, 2),
                "zero_crossing_rate": round(zcr_mean, 6),
                "spectral_smoothness_score": spectral_smoothness_score,
                "centroid_score": centroid_score,
                "zcr_score": zcr_score,
                "rhythm_score": rhythm_score
            },
            "source": "heuristic",
        }

    except Exception:
        return None


# ============================================================
#  对外主入口
# ============================================================

def analyze_voice(file_path, model=None):
    """
    分析音频文件是否为AI合成语音

    推理路径：指定/默认 ML 模型 → 启发式规则 → 文件信息 fallback

    Args:
        file_path: 音频文件路径
        model: 模型名，None/default/baseline 用 voice_baseline.joblib；
               可选 'gmm' / 'svm' / 'rf'（随机森林）

    Returns:
        dict: 包含risk_score, risk_level, detail, features的字典
              （ML 路径额外含 isFraud, confidence, fraudProbability, source）
    """
    # 检查文件是否存在
    if not os.path.exists(file_path):
        return {
            "risk_score": 0,
            "risk_level": "检测失败",
            "detail": f"音频文件不存在: {file_path}",
            "features": {}
        }

    explicit = model not in (None, '', 'default', 'baseline')

    # 1. 优先使用指定/默认 ML 模型预测
    if explicit:
        # 显式选模型：权重缺失直接报错，不静默回退到别的模型
        ml_result = _predict_with_ml(file_path, model)
        if ml_result is not None:
            return ml_result
        return {
            "risk_score": 0,
            "risk_level": "检测失败",
            "detail": f"语音模型 {model} 不可用，请确认模型已训练",
            "features": {},
            "source": "error",
        }

    ml_result = _predict_with_ml(file_path)
    if ml_result is not None:
        return ml_result

    # 2. 默认 ML 不可用 → 启发式规则
    heur_result = analyze_voice_heuristic(file_path)
    if heur_result is not None:
        return heur_result

    # 3. librosa 完全失败 → 文件信息 fallback
    return analyze_voice_fallback(file_path)


# ============================================================
#  可用模型清单（供 /api/models 接口使用）
# ============================================================

def list_voice_models():
    """返回当前已落盘、可切换的语音模型清单及测试指标"""
    # 指标优先从训练汇总 JSON 读（避免加载全部 pipeline）
    metrics_map = {}
    stats_json = os.path.join(
        _BASE_DIR, 'data', 'voice', 'stats', 'voice_models_results.json')
    try:
        with open(stats_json, 'r', encoding='utf-8') as f:
            stats = json.load(f)
        metrics_map = {k: v for k, v in stats.get('models', {}).items()}
        dataset = stats.get('dataset', '')
    except Exception:
        dataset = ''

    catalog = [
        ('gmm', 'voice_gmm.joblib', '高斯混合模型 GMM'),
        ('svm', 'voice_svm.joblib', '支持向量机 SVM'),
        ('rf', 'voice_rf.joblib', '随机森林 RandomForest'),
    ]
    available = []
    for key, fname, label in catalog:
        path = os.path.join(_MODELS_DIR, fname)
        if os.path.exists(path):
            available.append({
                'name': key,
                'label': label,
                'file': fname,
                'metrics': metrics_map.get(key, {}),
            })
    return {'modality': 'voice', 'dataset': dataset,
            'models': available,
            'default_file': DEFAULT_MODEL_FILE if os.path.exists(
                os.path.join(_MODELS_DIR, DEFAULT_MODEL_FILE)) else None}


def main():
    try:
        if len(sys.argv) < 2:
            result = {
                "risk_score": 0,
                "risk_level": "检测失败",
                "detail": "未提供音频文件路径",
                "features": {}
            }
            print(json.dumps(result, ensure_ascii=False))
            return

        file_path = sys.argv[1]
        result = analyze_voice(file_path)
        print(json.dumps(result, ensure_ascii=False))

    except Exception as e:
        error_result = {
            "risk_score": 0,
            "risk_level": "检测失败",
            "detail": f"语音检测异常: {str(e)}",
            "features": {}
        }
        print(json.dumps(error_result, ensure_ascii=False), file=sys.stderr)


if __name__ == "__main__":
    main()
