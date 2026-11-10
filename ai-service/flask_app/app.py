#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI Detection Microservice (Flask)
AI检测微服务

Provides HTTP API endpoints for all AI fraud detection capabilities.
This replaces the old Runtime.exec() based integration pattern.

提供所有AI诈骗检测能力的HTTP API接口。
替代旧的 Runtime.exec() 集成方式。

API Endpoints:
  GET  /api/health                - Health check 健康检查
  POST /api/detect/text           - Text fraud detection 文本诈骗检测
  POST /api/detect/voice          - Voice fraud detection 语音诈骗检测
  POST /api/detect/image          - Image fraud detection 图像诈骗检测
  POST /api/assess/risk           - Composite risk assessment 综合风险评估
  POST /api/blockchain/cert       - Blockchain certification 区块链存证
  POST /api/watermark/embed       - Embed watermark into image 嵌入数字水印
  POST /api/watermark/extract     - Extract watermark from image 提取数字水印

Architecture:
  Java Backend ──HTTP──► Flask Microservice ──► Python Detection Modules
                    (REST API)                    (text/voice/image)
"""

import os
import sys
import json
import tempfile
import logging
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS


def _disable_windows_quickedit():
    """Disable console QuickEdit mode on Windows (Windows 控制台防冻结).

    QuickEdit mode freezes the whole process whenever text gets selected
    in the console window (e.g. an accidental click). While frozen, Flask
    cannot serve any request until the user presses a key / Ctrl+C to
    cancel the selection. Disabling QuickEdit for this console fixes it.
    """
    if os.name != "nt":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-10)  # STD_INPUT_HANDLE
        mode = ctypes.c_uint()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            ENABLE_QUICK_EDIT_MODE = 0x0040
            ENABLE_EXTENDED_FLAGS = 0x0080
            new_mode = (mode.value & ~ENABLE_QUICK_EDIT_MODE) | ENABLE_EXTENDED_FLAGS
            kernel32.SetConsoleMode(handle, new_mode)
    except Exception:
        # Never fail startup just because the console tweak did not work
        pass


_disable_windows_quickedit()

# Add parent directory to path so we can import detection modules
# 把父目录加入路径，这样就能导入检测模块了
_PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)

# Import detection modules
from anti_fraud_text import (
    analyze_text, list_text_models, TextModelNotFoundError,
)
from anti_fraud_voice import (
    analyze_voice, list_voice_models, VoiceModelNotFoundError,
)
from anti_fraud_image import (
    analyze_image, list_image_models, ImageModelNotFoundError,
)
from risk_assessment import calculate_risk
from blockchain_cert import certify
from watermark import embed_watermark, extract_watermark

# 显式指定的模型不存在：API 统一返回 400；模型名非法时检测器抛 ValueError，
# 仅当请求确实带了 model 参数时才按 400 处理（见 _model_error_response）
_MODEL_NOT_FOUND_ERRORS = (
    TextModelNotFoundError, VoiceModelNotFoundError,
    ImageModelNotFoundError,
)


def _model_error_response(e, model_param):
    """模型选择类异常 → (response, 400)；其他异常返回 None 走 500"""
    if isinstance(e, _MODEL_NOT_FOUND_ERRORS):
        return _make_error(str(e), 400)
    if model_param and isinstance(e, ValueError):
        return _make_error(str(e), 400)
    return None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ai-service')

app = Flask(__name__)
CORS(app)


# ============================================================
#  Helper functions  辅助函数
# ============================================================

def _normalize_result(result):
    """
    Normalize result field names to use camelCase for consistency.
    Python modules use snake_case (risk_score), Java side expects both.
    We return both to maintain backward compatibility.

    归一化结果字段名，统一使用驼峰命名。
    Python模块用下划线命名（risk_score），Java端两种都认。
    我们同时返回两种，保持向后兼容。
    """
    normalized = dict(result)
    # Map snake_case to camelCase
    field_mapping = {
        'risk_score': 'riskScore',
        'risk_level': 'riskLevel',
        'face_detected': 'faceDetected',
        'ela_score': 'elaScore',
    }
    for snake, camel in field_mapping.items():
        if snake in normalized and camel not in normalized:
            normalized[camel] = normalized[snake]
    return normalized


def _save_uploaded_file(file_storage, suffix='.tmp'):
    """
    Save an uploaded file to a temporary location and return the path.
    将上传的文件保存到临时位置并返回路径。
    """
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    file_storage.save(tmp.name)
    tmp.close()
    return tmp.name


def _make_error(message, status_code=400):
    """Create a standardized error response."""
    return jsonify({
        'error': message,
        'riskScore': 0,
        'riskLevel': '检测失败',
        'detail': message
    }), status_code


# ============================================================
#  Health Check  健康检查
# ============================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """
    Health check endpoint for monitoring.
    Returns service status and available detection modules.

    健康检查接口，用于监控。
    返回服务状态和可用的检测模块。
    """
    modules = {
        'text': True,
        'voice': True,
        'image': True,
        'risk_assessment': True
    }

    # Check if optional dependencies are available
    # 检查可选依赖是否可用
    try:
        import librosa
        modules['voice_librosa'] = True
    except ImportError:
        modules['voice_librosa'] = False

    try:
        import cv2
        modules['image_opencv'] = True
    except ImportError:
        modules['image_opencv'] = False

    try:
        from PIL import Image
        modules['image_pil'] = True
    except ImportError:
        modules['image_pil'] = False

    # LLM 语义层状态：false 表示未读取到 API Key 或已被关闭
    try:
        from llm_detector import is_enabled as _llm_enabled
        modules['llm'] = bool(_llm_enabled())
    except Exception:
        modules['llm'] = False

    return jsonify({
        'status': 'ok',
        'service': 'ai-detection-service',
        'version': '1.0.0',
        'modules': modules
    })


# ============================================================
#  Available Models  可选模型清单（供前端下拉）
# ============================================================

@app.route('/api/models', methods=['GET'])
def list_models():
    """
    List trained/available detection models per modality.
    返回文字/语音/图片三个模态当前可用的模型清单（含测试集指标），
    供前端"选择模型测试"下拉框使用。
    """
    try:
        text_info = list_text_models()
        voice_info = list_voice_models()
        image_info = list_image_models()
        return jsonify({
            'status': 'ok',
            'text': {
                'dataset': text_info.get('dataset', ''),
                'default': text_info.get('default', 'ensemble'),
                'models': text_info.get('models', []),
            },
            'voice': {
                'dataset': voice_info.get('dataset', ''),
                'default_file': voice_info.get('default_file'),
                'models': voice_info.get('models', []),
            },
            'image': {
                'dataset': image_info.get('dataset', ''),
                'default_file': image_info.get('default_file'),
                'models': image_info.get('models', []),
            },
        })
    except Exception as e:
        logger.error(f"List models error: {str(e)}", exc_info=True)
        return _make_error(f'List models failed: {str(e)}', 500)


# ============================================================
#  Dataset Labels  数据集标签分布（供前端可视化）
# ============================================================

@app.route('/api/dataset/labels', methods=['GET'])
def dataset_labels():
    """
    返回 scripts/generate_dataset_labels.py 离线生成的标签统计 JSON。
    文件不存在时返回 404，由 Java 后端转换为 503 提示。
    """
    path = os.path.join(_PARENT_DIR, 'data', 'dataset_labels.json')
    if not os.path.exists(path):
        return jsonify({
            'error': 'dataset labels not generated',
            'detail': '请先运行 python scripts/generate_dataset_labels.py',
        }), 404
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
    except Exception as e:
        logger.error(f"Dataset labels read error: {str(e)}", exc_info=True)
        return jsonify({
            'error': 'dataset labels read failed',
            'detail': str(e),
        }), 500


# ============================================================
#  Text Detection  文本检测
# ============================================================

@app.route('/api/detect/text', methods=['POST'])
def detect_text():
    """
    Text fraud detection endpoint.
    文本诈骗检测接口。

    Request body:
        { "content": "text to analyze", "model": "baseline|bilstm|cnn|ensemble" }

    model 可选；缺省/ensemble 走历史多模型融合，其他值仅用指定模型（便于对比测试）。

    Response:
        {
            "riskScore": 85,
            "riskLevel": "高风险",
            "model": "ensemble",
            "modelLabel": "...",
            "detail": "...",
            "keywords": [...],
            "patterns": [...]
        }
    """
    model_param = None
    try:
        data = request.get_json()
        if not data or 'content' not in data:
            return _make_error('Missing required field: content')

        content = data.get('content', '')
        if not content or not content.strip():
            return _make_error('Content cannot be empty 内容不能为空')

        model_param = (data.get('model') or '').strip() or None
        logger.info(f"Text detection request, length={len(content)}, "
                    f"model={model_param or 'ensemble'}")

        result = analyze_text(content, model=model_param)
        result = _normalize_result(result)

        logger.info(f"Text detection result: score={result.get('riskScore')}, "
                    f"level={result.get('riskLevel')}, "
                    f"model={result.get('model')}")

        return jsonify(result)

    except Exception as e:
        model_err = _model_error_response(e, model_param)
        if model_err is not None:
            logger.warning(f"Text model selection error: {e}")
            return model_err
        logger.error(f"Text detection error: {str(e)}", exc_info=True)
        return _make_error(f'Text detection failed: {str(e)}', 500)


# ============================================================
#  Voice Detection  语音检测
# ============================================================

@app.route('/api/detect/voice', methods=['POST'])
def detect_voice():
    """
    Voice fraud detection endpoint.
    语音诈骗检测接口。

    Request: multipart/form-data
        file : 语音文件
        model: 可选，gmm / svm / rf（缺省走 voice_baseline 最佳模型）

    Response:
        {
            "riskScore": 45,
            "riskLevel": "中风险",
            "model": "gmm",
            "modelLabel": "高斯混合模型 GMM",
            "detail": "...",
            "features": { ... }
        }
    """
    model_param = None
    tmp_path = None
    try:
        if 'file' not in request.files:
            return _make_error('No file uploaded 请上传语音文件')

        file = request.files['file']
        if file.filename == '':
            return _make_error('Empty filename 文件名不能为空')

        model_param = (request.form.get('model') or '').strip() or None

        # Get file extension
        # 获取文件扩展名
        ext = os.path.splitext(file.filename)[1] or '.wav'
        tmp_path = _save_uploaded_file(file, suffix=ext)

        logger.info(f"Voice detection request: file={file.filename}, "
                    f"model={model_param or 'default'}")

        result = analyze_voice(tmp_path, model=model_param)
        result = _normalize_result(result)

        logger.info(f"Voice detection result: score={result.get('riskScore')}, "
                    f"level={result.get('riskLevel')}, "
                    f"model={result.get('model')}")

        return jsonify(result)

    except Exception as e:
        model_err = _model_error_response(e, model_param)
        if model_err is not None:
            logger.warning(f"Voice model selection error: {e}")
            return model_err
        logger.error(f"Voice detection error: {str(e)}", exc_info=True)
        return _make_error(f'Voice detection failed: {str(e)}', 500)
    finally:
        # Clean up temp file
        # 清理临时文件
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


# ============================================================
#  Image Detection  图像检测
# ============================================================

@app.route('/api/detect/image', methods=['POST'])
def detect_image():
    """
    Image fraud detection endpoint.
    图像诈骗检测接口。

    Request: multipart/form-data
        file : 图像文件
        model: 可选，logistic_regression / random_forest / svm
              （缺省走 image_baseline 最佳模型）

    Response:
        {
            "riskScore": 60,
            "riskLevel": "中风险",
            "model": "svm",
            "modelLabel": "支持向量机 RBF-SVM",
            "detail": "...",
            "faceDetected": true,
            "elaScore": 12.5
        }
    """
    model_param = None
    tmp_path = None
    try:
        if 'file' not in request.files:
            return _make_error('No file uploaded 请上传图像文件')

        file = request.files['file']
        if file.filename == '':
            return _make_error('Empty filename 文件名不能为空')

        model_param = (request.form.get('model') or '').strip() or None

        ext = os.path.splitext(file.filename)[1] or '.png'
        tmp_path = _save_uploaded_file(file, suffix=ext)

        logger.info(f"Image detection request: file={file.filename}, "
                    f"model={model_param or 'default'}")

        result = analyze_image(tmp_path, model=model_param)
        result = _normalize_result(result)

        logger.info(f"Image detection result: score={result.get('riskScore')}, "
                    f"level={result.get('riskLevel')}, "
                    f"model={result.get('model')}")

        return jsonify(result)

    except Exception as e:
        model_err = _model_error_response(e, model_param)
        if model_err is not None:
            logger.warning(f"Image model selection error: {e}")
            return model_err
        logger.error(f"Image detection error: {str(e)}", exc_info=True)
        return _make_error(f'Image detection failed: {str(e)}', 500)
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


# ============================================================
#  Composite Risk Assessment  综合风险评估
# ============================================================

@app.route('/api/assess/risk', methods=['POST'])
def assess_risk():
    """
    Composite risk assessment endpoint.
    综合风险评估接口。

    Request body:
        {
            "textScore": 60,
            "voiceScore": 75,
            "imageScore": 45
        }

    Response:
        {
            "riskScore": 60,
            "riskLevel": "中风险",
            "weights": {"text": 0.3, "voice": 0.35, "image": 0.35},
            "detail": "..."
        }
    """
    try:
        data = request.get_json()
        if not data:
            return _make_error('Request body is required 请求体不能为空')

        text_score = data.get('textScore', data.get('text_score', 0))
        voice_score = data.get('voiceScore', data.get('voice_score', 0))
        image_score = data.get('imageScore', data.get('image_score', 0))

        # Validate input
        try:
            text_score = int(text_score)
            voice_score = int(voice_score)
            image_score = int(image_score)
        except (ValueError, TypeError):
            return _make_error('Scores must be integers 风险分必须为整数')

        logger.info(f"Risk assessment: text={text_score}, voice={voice_score}, image={image_score}")

        result = calculate_risk(text_score, voice_score, image_score)
        result = _normalize_result(result)

        logger.info(f"Risk assessment result: score={result.get('riskScore')}, "
                    f"level={result.get('riskLevel')}")

        return jsonify(result)

    except Exception as e:
        logger.error(f"Risk assessment error: {str(e)}", exc_info=True)
        return _make_error(f'Risk assessment failed: {str(e)}', 500)


# ============================================================
#  Multimodal Risk Assessment (raw files)  多模态原始文件评估
# ============================================================

_FUSION_BUNDLE = None
_FUSION_BUNDLE_LOADED = False


def _get_fusion_bundle():
    """懒加载 models/fusion_model.joblib（完整晚期融合器）"""
    global _FUSION_BUNDLE, _FUSION_BUNDLE_LOADED
    if _FUSION_BUNDLE_LOADED:
        return _FUSION_BUNDLE
    _FUSION_BUNDLE_LOADED = True
    try:
        import joblib
        bundle_path = os.path.join(
            _PARENT_DIR, 'models', 'fusion_model.joblib')
        if os.path.exists(bundle_path):
            _FUSION_BUNDLE = joblib.load(bundle_path)
    except Exception as e:
        logger.warning(f"Fusion bundle unavailable: {e}")
        _FUSION_BUNDLE = None
    return _FUSION_BUNDLE


@app.route('/api/assess/risk-multimodal', methods=['POST'])
def assess_risk_multimodal():
    """
    Multimodal risk assessment from raw inputs.
    接收同一案例的原始文本+语音+图像，跑完整晚期融合（各模态模型 + 融合规则）。

    Request (multipart/form-data):
        text:   文本内容（普通表单字段）
        voice:  语音文件
        image:  图像文件

    Response:
        {
            "riskScore": 92,
            "riskLevel": "高风险",
            "isFraud": true,
            "confidence": 0.92,
            "strategy": "stacking",
            "modalityScores": {"text": 95, "voice": 80, "image": 60},
            "modalityProbability": {"text": 0.95, ...},
            "detail": "..."
        }
    """
    voice_tmp = None
    image_tmp = None
    try:
        text_content = request.form.get('text', '')
        if not text_content.strip():
            return _make_error('Missing field: text 缺少文本内容')
        if 'voice' not in request.files:
            return _make_error('Missing file: voice 缺少语音文件')
        if 'image' not in request.files:
            return _make_error('Missing file: image 缺少图像文件')

        voice_file = request.files['voice']
        image_file = request.files['image']
        if voice_file.filename == '' or image_file.filename == '':
            return _make_error('Empty filename 文件名不能为空')

        voice_ext = os.path.splitext(voice_file.filename)[1] or '.wav'
        image_ext = os.path.splitext(image_file.filename)[1] or '.png'
        voice_tmp = _save_uploaded_file(voice_file, suffix=voice_ext)
        image_tmp = _save_uploaded_file(image_file, suffix=image_ext)

        bundle = _get_fusion_bundle()
        if bundle is None:
            return _make_error(
                'Fusion model unavailable，请先运行 '
                'train_fusion_model.py 训练融合模型', 500)

        late_estimator = bundle.get('late_estimator')
        strategy = bundle.get('best_late_strategy',
                              bundle.get('strategy', 'unknown'))
        if late_estimator is None:
            return _make_error('Late fusion estimator missing', 500)

        logger.info(f"Multimodal fusion request, strategy={strategy}")

        out = late_estimator.predict_one_components(
            text_content, voice_tmp, image_tmp)

        fused_proba = out['fused_proba']
        risk_score = int(round(fused_proba * 100))
        is_fraud = fused_proba >= 0.5

        if risk_score == 0:
            risk_level = '无风险'
        elif risk_score < 30:
            risk_level = '低风险'
        elif risk_score < 70:
            risk_level = '中风险'
        else:
            risk_level = '高风险'

        result = {
            'riskScore': risk_score,
            'riskLevel': risk_level,
            'risk_score': risk_score,
            'risk_level': risk_level,
            'isFraud': bool(is_fraud),
            'confidence': round(fused_proba if is_fraud
                                else 1 - fused_proba, 4),
            'strategy': strategy,
            'modalityScores': out['modality_score'],
            'modalityProbability': out['modality_proba'],
            'detail': f"多模态晚期融合（{strategy}），综合诈骗概率 "
                      f"{round(fused_proba, 4)}",
            'source': 'late_fusion',
        }

        logger.info(f"Multimodal fusion result: score={risk_score}, "
                    f"level={risk_level}")
        return jsonify(result)

    except Exception as e:
        logger.error(f"Multimodal fusion error: {str(e)}", exc_info=True)
        return _make_error(f'Multimodal fusion failed: {str(e)}', 500)
    finally:
        for p in (voice_tmp, image_tmp):
            if p:
                try:
                    os.unlink(p)
                except OSError:
                    pass


# ============================================================
#  Blockchain Certification  区块链存证
# ============================================================

@app.route('/api/blockchain/cert', methods=['POST'])
def blockchain_certify():
    """
    Blockchain certification endpoint.
    区块链存证接口。

    Request body:
        {"data_content": "要存证的数据内容"}

    Response:
        {"success": true, "hash": "...", "block_index": 1, "timestamp": "...", "detail": "..."}
    """
    try:
        data = request.get_json()
        if not data or 'data_content' not in data:
            return _make_error('Missing required field: data_content 缺少必填字段 data_content')

        data_content = data.get('data_content', '')
        logger.info(f"Blockchain cert: data_content length={len(str(data_content))}")

        result = certify(data_content)

        logger.info(f"Blockchain cert result: success={result.get('success')}, "
                    f"block_index={result.get('block_index')}")
        return jsonify(result)

    except Exception as e:
        logger.error(f"Blockchain cert error: {str(e)}", exc_info=True)
        return _make_error(f'Cert failed: {str(e)}', 500)


# ============================================================
#  Digital Watermark  数字水印
# ============================================================

@app.route('/api/watermark/embed', methods=['POST'])
def watermark_embed():
    """
    Embed watermark into image.
    嵌入数字水印接口。

    Request (multipart/form-data):
        file: 图片文件（png/jpg/jpeg/bmp）
        watermark_text: 要嵌入的水印文本

    Response:
        {"success": true, "output_path": "...", "detail": "..."}
    """
    tmp_path = None
    out_path = None
    try:
        if 'file' not in request.files:
            return _make_error('Missing required file: file 缺少上传文件')
        if 'watermark_text' not in request.form:
            return _make_error('Missing required field: watermark_text 缺少水印文本')

        file = request.files['file']
        watermark_text = request.form['watermark_text']

        ext = os.path.splitext(file.filename)[1].lower() or '.png'
        if ext not in ('.png', '.jpg', '.jpeg', '.bmp'):
            return _make_error(f'Unsupported image format: {ext} 不支持的图片格式')

        tmp_path = _save_uploaded_file(file, suffix=ext)
        out_path = tmp_path.replace(ext, f'_wm{ext}')

        logger.info(f"Watermark embed: text='{watermark_text}', tmp={tmp_path}")

        result = embed_watermark(tmp_path, watermark_text, out_path)

        logger.info(f"Watermark embed result: success={result.get('success')}")
        return jsonify(result)

    except Exception as e:
        logger.error(f"Watermark embed error: {str(e)}", exc_info=True)
        return _make_error(f'Embed failed: {str(e)}', 500)
    finally:
        for p in (tmp_path, out_path):
            if p:
                try:
                    os.unlink(p)
                except OSError:
                    pass


@app.route('/api/watermark/extract', methods=['POST'])
def watermark_extract():
    """
    Extract watermark from image.
    提取数字水印接口。

    Request (multipart/form-data):
        file: 已嵌入水印的图片文件

    Response:
        {"success": true, "watermark": "...", "detail": "..."}
    """
    tmp_path = None
    try:
        if 'file' not in request.files:
            return _make_error('Missing required file: file 缺少上传文件')

        file = request.files['file']
        ext = os.path.splitext(file.filename)[1].lower() or '.png'
        if ext not in ('.png', '.jpg', '.jpeg', '.bmp'):
            return _make_error(f'Unsupported image format: {ext} 不支持的图片格式')

        tmp_path = _save_uploaded_file(file, suffix=ext)

        logger.info(f"Watermark extract: tmp={tmp_path}")

        result = extract_watermark(tmp_path)

        logger.info(f"Watermark extract result: success={result.get('success')}")
        return jsonify(result)

    except Exception as e:
        logger.error(f"Watermark extract error: {str(e)}", exc_info=True)
        return _make_error(f'Extract failed: {str(e)}', 500)
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


# ============================================================
#  Web Frontend Hosting  前端静态页面托管
# ============================================================

WEB_DIR = os.path.join(_PARENT_DIR, 'web')


@app.route('/')
def web_index():
    """平台首页（纯静态前端，无需 Node.js 构建）。"""
    return send_from_directory(WEB_DIR, 'index.html')


@app.route('/web/<path:filename>')
def web_static(filename):
    """前端静态资源（CSS / JS / 图片等）。"""
    return send_from_directory(WEB_DIR, filename)


# ============================================================
#  Main Entry  主入口
# ============================================================

if __name__ == '__main__':
    port = int(os.environ.get('AI_SERVICE_PORT', 5000))
    host = os.environ.get('AI_SERVICE_HOST', '0.0.0.0')
    debug = os.environ.get('AI_SERVICE_DEBUG', 'false').lower() == 'true'

    logger.info(f"Starting AI Detection Service on {host}:{port}")
    logger.info(f"Python path includes: {_PARENT_DIR}")

    app.run(host=host, port=port, debug=debug)
