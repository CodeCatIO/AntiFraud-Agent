#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
图像/视频伪造检测模块 (anti_fraud_image.py)
==========================================
用途：对图片进行伪造/篡改检测，包括人脸检测、ELA误差分析、AI生成痕迹检测等

推理优先级：
    1) ML 模型预测（models/image_baseline.joblib，ELA+传统特征 + SVM）
    2) 启发式规则 fallback（OpenCV：人脸/ELA/噪声；PIL 降级）

调用方式：
    python anti_fraud_image.py "图片文件路径"
输出：JSON格式到stdout
      ML 路径额外含 isFake, confidence, fakeProbability, source
依赖：Pillow, numpy, scikit-learn, joblib（OpenCV可选）
"""

import sys
import io
import json
import os


_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_MODELS_DIR = os.path.join(_BASE_DIR, 'models')

# ============================================================
#  可选模型注册表（models/ 下的 joblib 文件）
# ============================================================
# 三个可在页面上切换对比的模型；default/baseline 指向 image_baseline.joblib
# （train_image_models.py 会把它写成三模型中测试集 F1 最高者）
IMAGE_MODELS = {
    'logistic_regression': 'image_lr.joblib',
    'lr': 'image_lr.joblib',
    'random_forest': 'image_rf.joblib',
    'rf': 'image_rf.joblib',
    'svm': 'image_svm.joblib',
}
DEFAULT_MODEL_FILE = 'image_baseline.joblib'

# 模型缓存：{model_name: bundle}
_IMAGE_BUNDLE_CACHE = {}


class ImageModelNotFoundError(FileNotFoundError):
    """显式指定的图像模型权重不存在"""


def _resolve_model_file(model_name):
    """把请求里的模型名解析成 models/ 下的 joblib 文件名"""
    if model_name in (None, '', 'default', 'baseline'):
        return DEFAULT_MODEL_FILE
    key = str(model_name).lower()
    if key not in IMAGE_MODELS:
        raise ValueError(
            f"未知图像模型: {model_name}，可选: "
            f"{sorted(set(IMAGE_MODELS))}")
    return IMAGE_MODELS[key]


def _load_image_bundle(model_name=None):
    """按模型名懒加载 bundle dict 并缓存。

    默认模型（image_baseline.joblib）不存在时返回 None（走启发式降级）；
    显式指定的模型不存在时抛 ImageModelNotFoundError（避免静默测错模型）。
    """
    cache_key = model_name or 'default'
    if cache_key in _IMAGE_BUNDLE_CACHE:
        return _IMAGE_BUNDLE_CACHE[cache_key]

    import joblib
    fname = _resolve_model_file(model_name)
    path = os.path.join(_MODELS_DIR, fname)
    if not os.path.exists(path):
        if cache_key == 'default':
            _IMAGE_BUNDLE_CACHE[cache_key] = None
            return None
        raise ImageModelNotFoundError(
            f"图像模型 {model_name} 的权重文件不存在: {fname}，"
            f"请先运行 scripts/train_image_models.py")
    bundle = joblib.load(path)
    _IMAGE_BUNDLE_CACHE[cache_key] = bundle
    return bundle


def _get_image_model():
    """懒加载默认模型 image_baseline.joblib（保留旧调用兼容）"""
    return _load_image_bundle(None)


# ============================================================
#  ML 特征提取（须与 train_image_baseline.py 保持一致）
# ============================================================

def _compute_ela_map(img_rgb_uint8, quality=90):
    """计算 ELA（Error Level Analysis）误差图 (H, W, 3)"""
    from PIL import Image
    import numpy as np

    pil_img = Image.fromarray(img_rgb_uint8.astype(np.uint8), mode='RGB')
    buf = io.BytesIO()
    pil_img.save(buf, 'JPEG', quality=quality)
    buf.seek(0)
    recompressed = np.array(
        Image.open(buf).convert('RGB'), dtype=np.float64)
    return np.abs(img_rgb_uint8.astype(np.float64) - recompressed)


def _ela_features(ela_map):
    """ELA 图统计量（8 维）"""
    import numpy as np

    flat = ela_map.ravel()
    mean = float(np.mean(flat))
    std = float(np.std(flat))
    skew = float(np.mean(((flat - mean) / (std + 1e-8)) ** 3))
    return [
        mean, std, float(np.max(flat)), float(np.median(flat)),
        float(np.percentile(flat, 95)), float(np.percentile(flat, 99)),
        skew, float(np.mean(flat > 30)),
    ]


def _glcm_features(gray, levels=16):
    """灰度共生矩阵特征（4 维，纯 numpy 实现）"""
    import numpy as np

    g = (gray.astype(np.int32) // (256 // levels)).clip(0, levels - 1)
    g1 = g[:, :-1].ravel()
    g2 = g[:, 1:].ravel()

    glcm = np.zeros((levels, levels), dtype=np.float64)
    np.add.at(glcm, (g1, g2), 1)
    glcm += glcm.T
    total = glcm.sum()
    if total > 0:
        glcm /= total

    ii, jj = np.meshgrid(np.arange(levels), np.arange(levels),
                         indexing='ij')
    contrast = float((glcm * (ii - jj) ** 2).sum())
    homogeneity = float((glcm / (1.0 + np.abs(ii - jj))).sum())
    energy = float((glcm ** 2).sum())

    mu_i = float((glcm * ii).sum())
    mu_j = float((glcm * jj).sum())
    std_i = float(np.sqrt((glcm * (ii - mu_i) ** 2).sum()))
    std_j = float(np.sqrt((glcm * (jj - mu_j) ** 2).sum()))
    correlation = float(
        (glcm * (ii - mu_i) * (jj - mu_j)).sum() /
        (std_i * std_j + 1e-10))

    return [contrast, homogeneity, energy, correlation]


def _basic_features(img_rgb_uint8):
    """颜色 + 噪声 + 边缘统计（19 维）"""
    import cv2
    import numpy as np

    img = img_rgb_uint8.astype(np.float64)
    gray = cv2.cvtColor(img_rgb_uint8, cv2.COLOR_RGB2GRAY)

    rgb_mean = [img[:, :, c].mean() for c in range(3)]
    rgb_std = [img[:, :, c].std() for c in range(3)]

    hsv = cv2.cvtColor(img_rgb_uint8, cv2.COLOR_RGB2HSV).astype(np.float64)
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


def _build_ml_feature_vector(img_rgb_uint8, kind, ela_quality=90):
    """按训练时的特征组构建特征向量

    支持: ela / basic / ela_basic / full
    """
    ela_map = _compute_ela_map(img_rgb_uint8, quality=ela_quality)
    ela_feat = _ela_features(ela_map)

    if kind == 'ela':
        return ela_feat

    import cv2
    basic_feat = _basic_features(img_rgb_uint8)

    if kind == 'basic':
        return basic_feat
    elif kind == 'ela_basic':
        return ela_feat + basic_feat
    elif kind == 'full':
        gray = cv2.cvtColor(img_rgb_uint8, cv2.COLOR_RGB2GRAY)
        return ela_feat + basic_feat + _glcm_features(gray)

    # 未知类型默认 basic
    return basic_feat


def _predict_with_ml(file_path, model_name=None):
    """使用指定 ML 模型预测，返回结果 dict 或 None

    model_name: None/default -> image_baseline.joblib；
                也可传 logistic_regression / random_forest / svm。
    默认模型不存在时返回 None（走启发式降级）；显式模型缺失时抛异常。

    输出字段：risk_score, risk_level, detail, isFake, confidence,
              fakeProbability, face_detected, ela_score, features, source
    """
    model = _load_image_bundle(model_name)
    if model is None:
        return None

    pipeline = model.get('pipeline')
    feature_kind = model.get('feature_kind', 'basic')
    ela_quality = model.get('ela_quality', 90)
    model_key = model.get('model_name', model_name or 'image_baseline')
    model_label = model.get('model_label', {
        'logistic_regression': '逻辑回归',
        'random_forest': '随机森林',
        'svm': 'SVM',
    }.get(str(model_key), str(model_key)))
    if pipeline is None:
        return None

    try:
        from PIL import Image
        import numpy as np

        img_rgb = np.array(Image.open(file_path).convert('RGB'))
        feat = np.array(_build_ml_feature_vector(
            img_rgb, feature_kind, ela_quality)).reshape(1, -1)
    except Exception:
        return None

    try:
        pred = int(pipeline.predict(feat)[0])
        proba = pipeline.predict_proba(feat)[0]
        classes = getattr(pipeline, 'classes_', None)
        if classes is None and hasattr(pipeline, 'steps'):
            classes = pipeline.steps[-1][1].classes_
        if classes is None:
            classes = [0, 1]
        classes = list(classes)
        idx_fake = classes.index(1) if 1 in classes else 1
        fake_proba = float(proba[idx_fake]) if len(proba) > idx_fake else 0.5
    except Exception:
        return None

    # 风险分 = 伪造概率 × 100
    risk_score = int(round(fake_proba * 100))
    if risk_score < 30:
        risk_level = "低风险"
    elif risk_score < 70:
        risk_level = "中风险"
    else:
        risk_level = "高风险"

    # 附带原始 ELA 分数（便于展示）
    try:
        ela_raw_score = round(float(_compute_ela_map(img_rgb).mean()), 2)
    except Exception:
        ela_raw_score = 0.0

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "detail": f"ML模型预测（{feature_kind} 特征 + {model_label}），"
                  f"AI生成/篡改概率 {fake_proba:.2%}",
        "isFake": bool(pred == 1),
        "confidence": round(fake_proba if pred == 1 else 1 - fake_proba, 4),
        "fakeProbability": round(fake_proba, 4),
        "model": model_key,
        "modelLabel": model_label,
        "face_detected": False,
        "ela_score": ela_raw_score,
        "features": {
            "feature_kind": feature_kind,
            "model": model_key,
            "model_label": model_label,
        },
        "source": "ml",
    }


# ============================================================
#  启发式规则 fallback
# ============================================================

def analyze_image_with_pil(file_path):
    """
    使用PIL进行图像分析（无需OpenCV的降级方案，但更智能）

    检测维度：
    1. 文件元数据异常（AI生成图片通常缺乏相机信息）
    2. 色彩分布分析（AI生成图片色彩分布可能过于均匀）
    3. 噪声模式分析（AI生成图片噪声模式与真实照片不同）
    4. ELA误差分析（检测编辑痕迹）
    """
    risk_score = 0
    detail_parts = []
    face_detected = False
    ela_score = 0.0

    try:
        from PIL import Image
        import numpy as np

        img = Image.open(file_path)

        # 1. 元数据检测 - AI生成图片通常没有EXIF信息
        exif_data = img.info.get('exif', None)
        has_exif = exif_data is not None

        # 检查是否有相机相关元数据
        software = img.info.get('software', '')
        if software and any(s in software.lower() for s in ['photoshop', 'gimp', 'stable diffusion', 'dall-e', 'midjourney', 'ai', 'generated']):
            risk_score += 25
            detail_parts.append("图片元数据包含AI生成工具标识")

        if not has_exif:
            risk_score += 10
            detail_parts.append("缺少相机EXIF信息（AI生成图片常见特征）")

        # 2. 尺寸分析 - AI生成图片常有特定尺寸比例
        width, height = img.size
        aspect_ratio = width / height if height > 0 else 1

        # AI生成图片常见比例 1:1, 16:9, 或非标准比例
        if aspect_ratio == 1.0 and width >= 512:
            risk_score += 8
            detail_parts.append("正方形高分辨率图片（AI生成常见尺寸）")

        # 3. 色彩分布分析
        if img.mode in ('RGB', 'RGBA'):
            img_array = np.array(img.convert('RGB'))

            # 计算各通道统计量
            r_std = np.std(img_array[:, :, 0])
            g_std = np.std(img_array[:, :, 1])
            b_std = np.std(img_array[:, :, 2])

            avg_std = (r_std + g_std + b_std) / 3

            # AI生成图片色彩分布可能过于均匀
            if avg_std < 30:
                risk_score += 15
                detail_parts.append("色彩分布过于均匀（AI生成特征）")
            elif avg_std < 50:
                risk_score += 5

            # 4. 噪声模式分析
            # 用拉普拉斯算子近似
            from PIL import ImageFilter
            gray = img.convert('L')
            blurred = gray.filter(ImageFilter.GaussianBlur(radius=1))
            gray_array = np.array(gray, dtype=np.float64)
            blurred_array = np.array(blurred, dtype=np.float64)
            noise = np.abs(gray_array - blurred_array)
            noise_level = np.mean(noise)

            # AI生成图片噪声水平通常很低（过度平滑）
            if noise_level < 2:
                risk_score += 20
                detail_parts.append("图像噪声水平异常低（AI生成常见：过度平滑）")
            elif noise_level < 4:
                risk_score += 8
                detail_parts.append("图像噪声水平偏低")

            # 5. 边缘锐度分析
            # 检测是否有过于锐利的边缘（AI生成特征）
            edges_x = np.abs(np.diff(gray_array, axis=1))
            edges_y = np.abs(np.diff(gray_array, axis=0))
            edge_ratio = (np.sum(edges_x > 30) + np.sum(edges_y > 30)) / (width * height)

            if edge_ratio > 0.15:
                risk_score += 10
                detail_parts.append("边缘锐度异常（可能经过AI增强处理）")

            # 6. 皮肤色调检测（简单的人脸检测替代）
            r_ch = img_array[:, :, 0].astype(np.float64)
            g_ch = img_array[:, :, 1].astype(np.float64)
            b_ch = img_array[:, :, 2].astype(np.float64)

            # 简易肤色检测
            skin_mask = (
                (r_ch > 95) & (g_ch > 40) & (b_ch > 20) &
                (r_ch > g_ch) & (r_ch > b_ch) &
                (np.abs(r_ch - g_ch) > 15) &
                (r_ch - g_ch > 15)
            )
            skin_ratio = np.sum(skin_mask) / (width * height)

            if skin_ratio > 0.15:
                face_detected = True
                risk_score += 5
                detail_parts.append("检测到人物/人脸区域")

        # 7. ELA分析
        ela_score = perform_ela(file_path)
        if ela_score >= 0:
            if ela_score > 15:
                risk_score += 25
                detail_parts.append("ELA分析检测到明显编辑痕迹")
            elif ela_score > 8:
                risk_score += 12
                detail_parts.append("ELA分析检测到轻微编辑痕迹")
            elif ela_score < 1:
                risk_score += 10
                detail_parts.append("ELA误差极低（AI生成图片常见特征）")

    except ImportError:
        # PIL也不可用时的最简降级
        risk_score = 35
        detail_parts.append("降级模式，完整分析不可用")
    except Exception as e:
        risk_score = 35
        detail_parts.append("部分分析失败，降级评估")

    if not detail_parts:
        detail_parts.append("未检测到明显篡改或AI生成痕迹")

    # 限制上限
    risk_score = min(risk_score, 100)

    if risk_score >= 70:
        risk_level = "高风险"
    elif risk_score >= 40:
        risk_level = "中风险"
    else:
        risk_level = "低风险"

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "detail": "，".join(detail_parts) + "（启发式规则）",
        "face_detected": face_detected,
        "ela_score": ela_score if ela_score >= 0 else 0.0,
        "source": "heuristic",
    }


def perform_ela(image_path, quality=90):
    """执行ELA(Error Level Analysis)误差分析"""
    try:
        from PIL import Image
        import numpy as np
        import tempfile

        original = Image.open(image_path).convert('RGB')
        temp_path = tempfile.mktemp(suffix='.jpg')
        original.save(temp_path, 'JPEG', quality=quality)
        recompressed = Image.open(temp_path).convert('RGB')

        original_array = np.array(original, dtype=np.float64)
        recompressed_array = np.array(recompressed, dtype=np.float64)
        diff = np.abs(original_array - recompressed_array)
        ela_score = float(np.mean(diff))

        try:
            os.remove(temp_path)
        except Exception:
            pass

        return round(ela_score, 2)
    except Exception:
        return -1.0


def analyze_with_opencv(file_path):
    """OpenCV完整分析（启发式 fallback 路径）"""
    import cv2
    import numpy as np

    img = cv2.imread(file_path)
    if img is None:
        return analyze_image_with_pil(file_path)

    risk_score = 0
    detail_parts = []
    face_detected = False

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 人脸检测
    try:
        haar_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        if os.path.exists(haar_path):
            face_cascade = cv2.CascadeClassifier(haar_path)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
            face_count = len(faces)
            face_detected = face_count > 0
            if face_detected:
                detail_parts.append(f"检测到{face_count}个人脸")
    except Exception:
        pass

    # ELA分析
    ela_score = perform_ela(file_path)
    if ela_score > 15:
        risk_score += 25
        detail_parts.append("ELA分析检测到明显编辑痕迹")
    elif ela_score > 8:
        risk_score += 12
        detail_parts.append("ELA分析检测到轻微编辑痕迹")

    # 噪声分析
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    noise_level = np.var(laplacian)
    if noise_level < 50:
        risk_score += 15
        detail_parts.append("噪声模式异常（可能为AI生成）")

    if not detail_parts:
        detail_parts.append("未检测到明显篡改痕迹")
    if not face_detected:
        detail_parts.append("未检测到人脸")

    risk_score = min(risk_score, 100)
    if risk_score >= 70:
        risk_level = "高风险"
    elif risk_score >= 40:
        risk_level = "中风险"
    else:
        risk_level = "低风险"

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "detail": "，".join(detail_parts) + "（启发式规则）",
        "face_detected": face_detected,
        "ela_score": ela_score if ela_score >= 0 else 0.0,
        "source": "heuristic",
    }


# ============================================================
#  对外主入口
# ============================================================

def analyze_image(file_path, model=None):
    """主分析入口：指定/默认 ML 模型 → OpenCV 启发式 → PIL 降级

    Args:
        file_path: 图片路径
        model: 模型名，None/default/baseline 用 image_baseline.joblib；
               可选 'logistic_regression' / 'random_forest' / 'svm'

    Returns:
        dict: risk_score, risk_level, detail, face_detected, ela_score,
              source（ML 路径额外含 isFake, confidence, fakeProbability）
    """
    if not os.path.exists(file_path):
        return {
            "risk_score": 0,
            "risk_level": "检测失败",
            "detail": "图片文件不存在",
            "face_detected": False,
            "ela_score": 0.0
        }

    explicit = model not in (None, '', 'default', 'baseline')

    # 1. 指定模型：缺失直接报错，不静默回退
    if explicit:
        ml_result = _predict_with_ml(file_path, model)
        if ml_result is not None:
            return ml_result
        return {
            "risk_score": 0,
            "risk_level": "检测失败",
            "detail": f"图像模型 {model} 不可用，请确认模型已训练",
            "face_detected": False,
            "ela_score": 0.0,
            "source": "error",
        }

    # 1b. 默认 ML 模型预测
    ml_result = _predict_with_ml(file_path)
    if ml_result is not None:
        return ml_result

    # 2. ML 不可用 → OpenCV 启发式
    try:
        import cv2  # noqa: F401
        return analyze_with_opencv(file_path)
    except ImportError:
        # 3. OpenCV 不可用 → PIL 降级
        return analyze_image_with_pil(file_path)


# ============================================================
#  可用模型清单（供 /api/models 接口使用）
# ============================================================

def list_image_models():
    """返回当前已落盘、可切换的图像模型清单及测试指标"""
    metrics_map = {}
    stats_json = os.path.join(
        _BASE_DIR, 'data', 'image', 'stats', 'image_models_results.json')
    try:
        with open(stats_json, 'r', encoding='utf-8') as f:
            stats = json.load(f)
        metrics_map = {k: v for k, v in stats.get('models', {}).items()}
        dataset = stats.get('dataset', '')
    except Exception:
        dataset = ''

    catalog = [
        ('logistic_regression', 'image_lr.joblib', '逻辑回归 LogisticRegression'),
        ('random_forest', 'image_rf.joblib', '随机森林 RandomForest'),
        ('svm', 'image_svm.joblib', '支持向量机 RBF-SVM'),
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
    return {'modality': 'image', 'dataset': dataset,
            'models': available,
            'default_file': DEFAULT_MODEL_FILE if os.path.exists(
                os.path.join(_MODELS_DIR, DEFAULT_MODEL_FILE)) else None}


def main():
    try:
        if len(sys.argv) < 2:
            result = {
                "risk_score": 0,
                "risk_level": "检测失败",
                "detail": "未提供图片文件路径",
                "face_detected": False,
                "ela_score": 0.0
            }
            print(json.dumps(result, ensure_ascii=False))
            return

        file_path = sys.argv[1]
        result = analyze_image(file_path)
        print(json.dumps(result, ensure_ascii=False))

    except Exception as e:
        error_result = {
            "risk_score": 0,
            "risk_level": "检测失败",
            "detail": "图像检测异常：" + str(e),
            "face_detected": False,
            "ela_score": 0.0
        }
        print(json.dumps(error_result, ensure_ascii=False))


if __name__ == "__main__":
    main()
