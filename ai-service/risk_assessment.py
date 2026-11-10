#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
综合风险评估模块 (risk_assessment.py)
=====================================
用途：根据文本、语音、图像各模块的风险分，计算综合风险等级

推理优先级：
    1) 学习型晚期融合（models/fusion_model.joblib 的 score_meta，
       在三模态 P(fraud) 上训练的 LogisticRegression 元模型）
    2) 固定权重加权求和 fallback（text 0.30 / voice 0.35 / image 0.35）

调用方式：
    python risk_assessment.py text_score voice_score image_score
    例如: python risk_assessment.py 60 75 45
输出：JSON格式到stdout，包含 risk_score, risk_level, weights, detail,
      source, modalityScores, confidence
"""

import sys
import json
import os


# 固定权重（fallback，同时作为输出中默认权重展示）
WEIGHTS = {
    "text": 0.3,
    "voice": 0.35,
    "image": 0.35
}

# ---- 学习型融合模型懒加载 ----
_FUSION_MODEL = None
_FUSION_MODEL_LOADED = False


def _get_fusion_model():
    """懒加载 models/fusion_model.joblib

    Returns:
        dict or None
    """
    global _FUSION_MODEL, _FUSION_MODEL_LOADED
    if _FUSION_MODEL_LOADED:
        return _FUSION_MODEL
    _FUSION_MODEL_LOADED = True

    try:
        import joblib
        # risk_assessment.py 位于 ai-service/ 根目录，models 同级
        model_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(model_dir, 'models',
                                  'fusion_model.joblib')
        if os.path.exists(model_path):
            _FUSION_MODEL = joblib.load(model_path)
        else:
            _FUSION_MODEL = None
    except Exception:
        _FUSION_MODEL = None
    return _FUSION_MODEL


def _risk_level_from_score(risk_score):
    """分数 → 等级"""
    if risk_score == 0:
        return "无风险"
    elif risk_score < 30:
        return "低风险"
    elif risk_score < 70:
        return "中风险"
    return "高风险"


def _build_detail(text_score, voice_score, image_score, risk_score):
    """生成人类可读详情（与原逻辑保持一致）"""
    detail_parts = []

    if text_score >= 60:
        detail_parts.append("文本内容存在较高诈骗风险")
    elif text_score >= 30:
        detail_parts.append("文本内容存在可疑关键词")

    if voice_score >= 60:
        detail_parts.append("语音存在AI合成嫌疑")
    elif voice_score >= 30:
        detail_parts.append("语音特征略有异常")

    if image_score >= 60:
        detail_parts.append("图像存在篡改痕迹")
    elif image_score >= 30:
        detail_parts.append("图像略有异常")

    if not detail_parts:
        return "综合多模态分析，未检测到明显诈骗风险"
    elif risk_score < 70:
        return "，".join(detail_parts) + "；综合评估为中等诈骗风险"
    return "，".join(detail_parts) + "；综合评估为高度诈骗风险，请提高警惕"


def calculate_risk(text_score, voice_score, image_score):
    """
    计算综合风险分

    学习型融合优先（stacking 元模型），模型不可用时回退固定权重加权。

    Args:
        text_score: 文本检测风险分 (0-100)
        voice_score: 语音检测风险分 (0-100)
        image_score: 图像检测风险分 (0-100)

    Returns:
        dict: 综合风险评估结果
    """
    # 输入范围约束
    text_score = max(0, min(100, int(text_score)))
    voice_score = max(0, min(100, int(voice_score)))
    image_score = max(0, min(100, int(image_score)))

    modality_scores = {
        "text": text_score,
        "voice": voice_score,
        "image": image_score,
    }

    # 1) 学习型晚期融合
    fused_proba = None
    model = _get_fusion_model()
    if model is not None:
        score_meta = model.get('score_meta')
        if score_meta is not None:
            try:
                # 元模型在 P(fraud)（0-1）上训练，分数先除 100
                x = [[text_score / 100.0,
                      voice_score / 100.0,
                      image_score / 100.0]]
                fused_proba = float(score_meta.predict_proba(x)[0][1])
            except Exception:
                fused_proba = None

    # 2) fallback：固定权重加权
    if fused_proba is not None:
        risk_score = int(round(fused_proba * 100))
        source = "learned_fusion"
    else:
        risk_score = round(
            text_score * WEIGHTS["text"] +
            voice_score * WEIGHTS["voice"] +
            image_score * WEIGHTS["image"]
        )
        fused_proba = risk_score / 100.0
        source = "fixed_weights"

    risk_level = _risk_level_from_score(risk_score)
    detail = _build_detail(text_score, voice_score, image_score,
                          risk_score)
    if source == "learned_fusion":
        detail += "（学习型融合）"
    else:
        detail += "（固定权重）"

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "weights": WEIGHTS,
        "detail": detail,
        "source": source,
        "modalityScores": modality_scores,
        "confidence": round(fused_proba if risk_score >= 50
                            else 1 - fused_proba, 4),
    }


def main():
    try:
        if len(sys.argv) < 4:
            result = {
                "risk_score": 0,
                "risk_level": "评估失败",
                "weights": WEIGHTS,
                "detail": "参数不足，用法: python risk_assessment.py "
                          "text_score voice_score image_score"
            }
            print(json.dumps(result, ensure_ascii=False))
            return

        text_score = int(sys.argv[1])
        voice_score = int(sys.argv[2])
        image_score = int(sys.argv[3])

        result = calculate_risk(text_score, voice_score, image_score)
        print(json.dumps(result, ensure_ascii=False))

    except ValueError:
        error_result = {
            "risk_score": 0,
            "risk_level": "评估失败",
            "weights": WEIGHTS,
            "detail": "参数格式错误，风险分应为0-100的整数"
        }
        print(json.dumps(error_result, ensure_ascii=False), file=sys.stderr)

    except Exception as e:
        error_result = {
            "risk_score": 0,
            "risk_level": "评估失败",
            "weights": WEIGHTS,
            "detail": f"风险评估异常: {str(e)}"
        }
        print(json.dumps(error_result, ensure_ascii=False), file=sys.stderr)


if __name__ == "__main__":
    main()
