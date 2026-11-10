#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文本诈骗检测模块 (anti_fraud_text.py)
用途：对文本内容进行诈骗风险检测，包括关键词匹配、句式分析等
调用方式：
    python anti_fraud_text.py "待检测文本内容"
输出：JSON格式到stdout
依赖：jieba
"""

import sys
import json
import os
import re
import math

import joblib
import pandas as pd
import jieba

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_MODELS_DIR = os.path.join(_BASE_DIR, 'models')

# 模块加载时尝试加载训练好的 ML 模型；不存在或加载失败时回退到关键词+正则逻辑
_ML_PIPELINE = None
try:
    _MODEL_PATH = os.path.join(_MODELS_DIR, 'text_baseline.joblib')
    if os.path.exists(_MODEL_PATH):
        _ML_PIPELINE = joblib.load(_MODEL_PATH)
except Exception:
    _ML_PIPELINE = None

# ============================================================
#  可选文本模型注册表
# ============================================================
# baseline：TF-IDF n-gram + LinearSVC（text_baseline.joblib，模块级已加载）
# bilstm ：BiLSTM+Attention（train_text_bilstm.py 产物）
# cnn    ：TextCNN 多尺度卷积（train_text_cnn.py 产物）
# default/ensemble：规则 + ML + BiLSTM + LLM 多层融合（历史默认行为，不变）
TEXT_MODEL_ALIASES = {
    'baseline': 'baseline',
    'tfidf': 'baseline',
    'bilstm': 'bilstm',
    'text_bilstm': 'bilstm',
    'cnn': 'cnn',
    'text_cnn': 'cnn',
    'ensemble': 'ensemble',
    'default': 'ensemble',
}
TEXT_MODEL_LABELS = {
    'baseline': 'TF-IDF n-gram + LinearSVC',
    'bilstm': 'BiLSTM + Attention',
    'cnn': 'TextCNN 多尺度卷积',
    'ensemble': '多模型融合（规则+ML+BiLSTM+LLM）',
}
_DEEP_WEIGHT_FILES = {
    'bilstm': ('text_bilstm.pt', 'text_bilstm_vocab.json', 'text_bilstm_meta.json'),
    'cnn': ('text_cnn.pt', 'text_cnn_vocab.json', 'text_cnn_meta.json'),
}

# 深度模型缓存：{name: {'model', 'vocab', 'config'}}
_DEEP_CACHE = {}


class TextModelNotFoundError(FileNotFoundError):
    """显式指定的文本模型权重不存在"""


def _load_deep_model(name, raise_on_missing=False):
    """懒加载指定深度模型（bilstm / cnn），结果缓存。

    raise_on_missing=False（融合路径）：权重缺失/加载失败返回 None；
    raise_on_missing=True （显式选择）：权重缺失抛 TextModelNotFoundError。
    """
    if name in _DEEP_CACHE:
        return _DEEP_CACHE[name]

    w_file, v_file, m_file = _DEEP_WEIGHT_FILES[name]
    weight_path = os.path.join(_MODELS_DIR, w_file)
    vocab_path = os.path.join(_MODELS_DIR, v_file)
    meta_path = os.path.join(_MODELS_DIR, m_file)

    if not (os.path.exists(weight_path) and os.path.exists(vocab_path)):
        if raise_on_missing:
            raise TextModelNotFoundError(
                f"文本模型 {name} 的权重文件缺失（{w_file} / {v_file}），"
                f"请先运行对应训练脚本")
        return None

    try:
        import torch
        # 从训练脚本目录导入模型定义
        if os.path.join(_BASE_DIR, 'scripts') not in sys.path:
            sys.path.insert(0, os.path.join(_BASE_DIR, 'scripts'))

        with open(vocab_path, 'r', encoding='utf-8') as f:
            vocab = json.load(f)
        config = {}
        if os.path.exists(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as f:
                config = json.load(f).get('config', {})

        pad_idx = vocab.get('<pad>', 0)
        if name == 'bilstm':
            from train_text_bilstm import BiLSTMAttn
            model = BiLSTMAttn(
                vocab_size=len(vocab),
                embed_dim=config.get('embed_dim', 128),
                hidden_dim=config.get('hidden_dim', 128),
                num_layers=config.get('num_layers', 2),
                num_classes=2,
                dropout=config.get('dropout', 0.5),
                pad_idx=pad_idx,
            )
        else:  # cnn
            from train_text_cnn import TextCNN
            model = TextCNN(
                vocab_size=len(vocab),
                embed_dim=config.get('embed_dim', 128),
                num_filters=config.get('num_filters', 64),
                kernel_sizes=tuple(config.get('kernel_sizes', [2, 3, 4, 5])),
                num_classes=2,
                dropout=config.get('dropout', 0.5),
                pad_idx=pad_idx,
            )
        state = torch.load(weight_path, map_location='cpu')
        model.load_state_dict(state)
        model.eval()

        bundle = {'model': model, 'vocab': vocab, 'config': config}
        _DEEP_CACHE[name] = bundle
        return bundle
    except Exception:
        if raise_on_missing:
            raise
        return None


def _deep_predict(content, name='bilstm'):
    """用指定深度模型预测诈骗概率；权重缺失返回 None（融合路径静默跳过）"""
    bundle = _load_deep_model(name)
    if bundle is None:
        return None

    import torch
    from deep_text_common import encode_text

    vocab, config, model = bundle['vocab'], bundle['config'], bundle['model']
    max_len = config.get('max_len', 128)
    ids = torch.tensor([encode_text(content, vocab, max_len)],
                       dtype=torch.long)
    with torch.no_grad():
        logits = model(ids)
        p = torch.softmax(logits, dim=1)[0]
        p_fraud = float(p[1])

    risk_score = max(0, min(100, round(p_fraud * 100)))
    if risk_score >= 70:
        risk_level = "高风险"
    elif risk_score >= 40:
        risk_level = "中风险"
    else:
        risk_level = "低风险"

    arch = "BiLSTM+Attention" if name == 'bilstm' else "TextCNN 多尺度卷积"
    return {
        "riskScore": risk_score,
        "riskLevel": risk_level,
        "detail": f"深度学习模型预测（{arch}），诈骗概率 {p_fraud:.2%}",
        "keywords": [],
        "patterns": []
    }


# LLM 语义检测层（DeepSeek API）懒加载；未配置 key / 关闭时为 None
_llm_analyze = None
try:
    from llm_detector import analyze_text_llm as _llm_analyze
except ImportError:
    _llm_analyze = None

# 诈骗关键词库（按严重程度分级）
HIGH_RISK_KEYWORDS = [
    "转账", "汇款", "打款", "汇钱", "汇入", "转钱", "打钱",
    "验证码", "密码", "账号安全", "账户异常", "冻结",
    "中奖", "领取", "兑换码", "免费领取", "恭喜您",
    "公检法", "公安局", "警方", "检察院", "法院传票",
    "安全账户", "监管账户", "资金清查",
    "刷单", "返利", "佣金", "日赚", "躺赚",
    "贷款", "低息", "无抵押", "免审核", "秒放款",
    "投资理财", "高收益", "稳赚不赔", "内幕消息",
    "点击链接", "立即申请", "限时", "最后机会",
    # 求职缴费类诈骗：正规单位不会在入职前收取任何费用
    "培训费", "押金", "保证金", "工本费", "体检费", "服装费",
    "激活费", "解冻费", "诚意金", "入职费", "报名费", "材料费",
    "提前缴纳", "垫付", "刷信誉",
    # 个人信息收集类诈骗：以福利/养老/补贴为诱饵骗取身份信息
    "身份信息", "身份证号", "个人信息", "银行卡号", "征信修复",
]

MEDIUM_RISK_KEYWORDS = [
    "优惠", "折扣", "红包", "返现", "满减",
    "加微信", "加QQ", "私聊", "扫码",
    "客服", "专员", "经理", "老师带",
    "兼职", "副业", "网赚", "在家做",
    "信用卡", "提额", "代办",
    "紧急", "马上", "尽快", "务必",
    "代开", "代办", "包过",
    # 求职类弱信号：单独出现不判险，配合缴费词才升级
    "招聘", "入职", "缴纳", "诚聘", "急招", "手续费",
]

# 诈骗句式模式
FRAUD_PATTERNS = [
    (r"您的.{0,5}(账户|银行卡|信用卡).{0,5}(异常|冻结|风险)", 30, "账户异常类诈骗话术"),
    (r"(点击|打开|复制).{0,10}(链接|网址|地址)", 20, "诱导点击链接"),
    (r"(转账|汇款|打款).{0,15}(安全账户|监管账户|指定账户)", 35, "诱导转账至指定账户"),
    (r"(恭喜|恭喜您).{0,10}(中奖|获得|领取)", 30, "中奖诈骗话术"),
    (r"(公安局|检察院|法院).{0,10}(调查|案件|涉案)", 30, "冒充公检法"),
    (r"(日赚|月入|年薪).{0,5}\d+(万|千|块)", 25, "虚假高收益承诺"),
    (r"(刷单|刷信誉|刷销量).{0,10}(返利|佣金|工资)", 30, "刷单诈骗"),
    (r"(低息|免息|无抵押).{0,10}(贷款|借款|放款)", 25, "虚假贷款"),
    (r"验证码.{0,10}(告诉|发送|告知|提供)", 25, "索要验证码"),
    # 求职缴费类诈骗句式
    (r"(缴纳|支付|交).{0,6}(培训费|押金|保证金|工本费|体检费|服装费|激活费|解冻费|注册费|报名费|材料费)", 35, "入职/办理前要求缴纳费用"),
    (r"(招聘|录用|录取|急招|诚聘).{0,35}(缴纳|押金|保证金|培训费|工本费|体检费|缴费|付费)", 30, "招聘环节涉及缴费（典型求职诈骗）"),
    (r"(入职|上岗|实习).{0,15}(必须|需要|先|提前|请).{0,6}(缴纳|交|支付|付费)", 30, "入职前强制缴费"),
    (r"(先|提前|预付).{0,4}(缴纳|支付|交|付).{0,4}\d+", 25, "要求预先支付钱款"),
    # 个人信息收集类诈骗句式（养老/福利/补贴骗局）
    (r"(免费|0元|无需缴费|国家补贴|政策扶持|高额补贴|专项补贴).{0,12}(接收|收养|抚养|照护|领取|申请|办理|享受)", 30, "以免费福利为诱饵"),
    (r"(免费|0元).{0,10}(接收|收养|抚养|照护).{0,6}(老人|老年|长者|孩子|儿童)", 30, "免费照护老人/儿童骗局"),
    (r"(填写|提供|登记|上传|发送).{0,8}(身份|身份证|个人信息|银行卡|验证码|家庭住址|联系方式)", 30, "诱导填写/提供个人敏感信息"),
    (r"(高龄|养老|养老金|低保|残疾人).{0,6}(补贴|津贴|补助).{0,25}(身份|身份证|银行卡|办理|申领)", 30, "冒充政府补贴申领骗局"),
]


def _ml_predict(content):
    """用 ML pipeline 预测诈骗概率，返回与 analyze_text 兼容的结果 dict。

    Pipeline 接受 DataFrame（含 text + tokens 列），输出概率或决策值。
    label 顺序与训练时一致：0=正常, 1=诈骗。
    """
    tokens = ' '.join(jieba.lcut(content))
    X = pd.DataFrame([{'text': content, 'tokens': tokens}])

    if hasattr(_ML_PIPELINE, 'predict_proba'):
        proba = _ML_PIPELINE.predict_proba(X)[0]
        p_fraud = float(proba[1]) if len(proba) > 1 else float(proba[0])
    elif hasattr(_ML_PIPELINE, 'decision_function'):
        d = float(_ML_PIPELINE.decision_function(X)[0])
        # 防止 math.exp 溢出
        p_fraud = 1.0 / (1.0 + math.exp(-d)) if -700 < d < 700 else (1.0 if d > 0 else 0.0)
    else:
        pred = int(_ML_PIPELINE.predict(X)[0])
        p_fraud = 1.0 if pred == 1 else 0.0

    risk_score = max(0, min(100, round(p_fraud * 100)))
    if risk_score >= 70:
        risk_level = "高风险"
    elif risk_score >= 40:
        risk_level = "中风险"
    else:
        risk_level = "低风险"

    return {
        "riskScore": risk_score,
        "riskLevel": risk_level,
        "detail": f"ML模型预测（TF-IDF + 分类器），诈骗概率 {p_fraud:.2%}",
        "keywords": [],
        "patterns": []
    }


def _keyword_result(content):
    """关键词 + 正则兜底检测，返回与 analyze_text 兼容的结果 dict"""
    risk_score = 0
    matched_keywords = []
    matched_patterns = []

    # 1. 关键词匹配
    try:
        import jieba
        words = list(jieba.cut(content))
        word_set = set(words)
    except ImportError:
        # jieba不可用时用简单字符串匹配
        word_set = set(content)
        words = list(content)

    for kw in HIGH_RISK_KEYWORDS:
        if kw in content:
            risk_score += 15
            matched_keywords.append(kw)

    for kw in MEDIUM_RISK_KEYWORDS:
        if kw in content:
            risk_score += 8
            matched_keywords.append(kw)

    # 2. 诈骗句式匹配
    for pattern, score, desc in FRAUD_PATTERNS:
        if re.search(pattern, content):
            risk_score += score
            matched_patterns.append(desc)

    # 3. 紧急程度分析（大量感叹号、紧急词）
    exclamation_count = content.count("！") + content.count("!")
    if exclamation_count >= 3:
        risk_score += 10
        matched_patterns.append("大量使用感叹号制造紧迫感")

    # 4. 链接检测
    url_pattern = r'https?://[^\s]+|www\.[^\s]+'
    urls = re.findall(url_pattern, content)
    if urls:
        risk_score += 10
        matched_patterns.append("包含可疑链接")

    # 5. 电话号码检测
    phone_pattern = r'1[3-9]\d{9}|400[-\s]?\d{3}[-\s]?\d{4}'
    phones = re.findall(phone_pattern, content)
    if phones:
        risk_score += 5
        matched_patterns.append("包含联系电话")

    # 限制上限
    risk_score = min(risk_score, 100)

    # 确定风险等级
    if risk_score >= 70:
        risk_level = "高风险"
    elif risk_score >= 40:
        risk_level = "中风险"
    else:
        risk_level = "低风险"

    # 生成详细说明
    detail_parts = []
    if matched_keywords:
        detail_parts.append("命中关键词：" + "、".join(matched_keywords[:5]))
    if matched_patterns:
        detail_parts.append("匹配诈骗模式：" + "、".join(matched_patterns[:3]))
    if not detail_parts:
        detail_parts.append("未检测到明显诈骗特征，文本内容相对安全")

    # 去重关键词
    seen = set()
    unique_keywords = []
    for kw in matched_keywords:
        if kw not in seen:
            seen.add(kw)
            unique_keywords.append(kw)

    return {
        "riskScore": risk_score,
        "riskLevel": risk_level,
        "detail": "；".join(detail_parts),
        "keywords": unique_keywords[:8],
        "patterns": matched_patterns[:5]
    }


def _combine_results(primary, fallback):
    """合并模型结果与关键词结果，取最高分（反诈场景宁可误报不可漏报）。

    - 风险分取两者最大值，等级随分值
    - 关键词/句式命中合并去重，保证可解释性
    - detail 取分高的一方；若关键词分更高，说明模型漏判，显式标注
    """
    merged = dict(primary)
    if fallback["riskScore"] > primary["riskScore"]:
        merged["riskScore"] = fallback["riskScore"]
        merged["riskLevel"] = fallback["riskLevel"]
        merged["detail"] = fallback["detail"] + f"（模型原始评分 {primary['riskScore']}，关键词规则已提升风险等级）"
    merged["keywords"] = list(dict.fromkeys(
        primary.get("keywords", []) + fallback.get("keywords", [])))[:8]
    merged["patterns"] = list(dict.fromkeys(
        primary.get("patterns", []) + fallback.get("patterns", [])))[:5]
    return merged


def _merge_results(results):
    """多层检测结果融合：分数取最高，关键词/句式并集去重（宁可误报不可漏报）。

    results 中每个元素都是 analyze_text 兼容的 dict，至少含 riskScore/riskLevel。
    detail 取最高分层的结果；若胜者是 LLM 层，补充规则层命中情况。
    """
    winner = max(results, key=lambda r: r["riskScore"])
    merged = dict(winner)

    keywords, patterns = [], []
    for r in results:
        keywords.extend(r.get("keywords", []))
        patterns.extend(r.get("patterns", []))
    merged["keywords"] = list(dict.fromkeys(keywords))[:8]
    merged["patterns"] = list(dict.fromkeys(patterns))[:5]

    # 若关键词层分数更高（模型漏判），在 detail 中保留规则证据
    rule_layer = results[0]
    if winner is not rule_layer and rule_layer["riskScore"] > 0:
        merged["detail"] = winner["detail"] + "；规则层命中：" + rule_layer["detail"]
    return merged


def analyze_text(content, model=None):
    """
    分析文本是否包含诈骗内容

    Args:
        content: 待检测文本
        model: 使用哪个模型。
               None / 'default' / 'ensemble'（默认）：规则 + ML + BiLSTM
                   + LLM 多层融合，取最高分（历史行为，保持不变）；
               'baseline'（'tfidf'）：仅 TF-IDF n-gram + LinearSVC；
               'bilstm'：仅 BiLSTM+Attention；
               'cnn'（'text_cnn'）：仅 TextCNN。
               显式选择单模型时只返回该模型的结果，便于模型间对比测试；
               指定模型不可用时抛 TextModelNotFoundError（由 API 返回 400）。

    Returns:
        dict: 检测结果
    """
    if not content or not content.strip():
        return {
            "riskScore": 0,
            "riskLevel": "无风险",
            "detail": "输入内容为空",
            "keywords": [],
            "patterns": []
        }

    # ---------- 显式选择单模型：只跑该模型，不与规则融合 ----------
    if model is not None and str(model).strip():
        key = TEXT_MODEL_ALIASES.get(str(model).strip().lower())
        if key is None:
            raise ValueError(
                f"未知文本模型: {model}，可选: baseline / bilstm / cnn / ensemble")

        if key == 'ensemble':
            pass  # 落到下面的默认融合逻辑
        elif key == 'baseline':
            if _ML_PIPELINE is None:
                raise TextModelNotFoundError(
                    "文本模型 baseline 的权重 text_baseline.joblib 缺失，"
                    "请先运行 scripts/train_text_baseline.py")
            result = _ml_predict(content)
            result["model"] = 'baseline'
            result["modelLabel"] = TEXT_MODEL_LABELS['baseline']
            return result
        else:  # bilstm / cnn
            # 权重缺失时抛 TextModelNotFoundError
            _load_deep_model(key, raise_on_missing=True)
            result = _deep_predict(content, key)
            if result is None:  # 理论不会发生（上面已校验/加载）
                raise TextModelNotFoundError(f"文本模型 {key} 加载失败")
            result["model"] = key
            result["modelLabel"] = TEXT_MODEL_LABELS[key]
            return result

    # ---------- 默认：多层融合（规则始终兜底） ----------
    # 规则检测始终运行（兜底 + 可解释性）
    keyword_result = _keyword_result(content)

    # 收集所有可用层的结果，最终融合取最高分
    results = [keyword_result]

    # 层2：传统 ML 模型（泛化最稳）
    if _ML_PIPELINE is not None:
        try:
            results.append(_ml_predict(content))
        except Exception:
            pass  # 出错则跳过该层

    # 层2备选：深度学习模型（BiLSTM+Attention）
    try:
        deep_result = _deep_predict(content, 'bilstm')
        if deep_result is not None:
            results.append(deep_result)
    except Exception:
        pass  # 出错则跳过该层

    # 层3：LLM 语义分析（DeepSeek，可识别全新话术；失败/超时自动跳过）
    if _llm_analyze is not None:
        try:
            llm_result = _llm_analyze(content)
            if llm_result is not None:
                results.append(llm_result)
        except Exception:
            pass  # LLM 不可用不影响主流程

    if len(results) == 1:
        merged = keyword_result
    else:
        merged = _merge_results(results)
    merged["model"] = 'ensemble'
    merged["modelLabel"] = TEXT_MODEL_LABELS['ensemble']
    return merged


# ============================================================
#  可用模型清单（供 /api/models 接口使用）
# ============================================================

def list_text_models():
    """返回当前可用的文本模型清单及测试指标"""
    stats_dir = os.path.join(_BASE_DIR, 'data', 'text', 'stats')

    # baseline 指标：读 baseline_results.json 的 best_combo/best_score
    baseline_metrics = {}
    try:
        with open(os.path.join(stats_dir, 'baseline_results.json'),
                  'r', encoding='utf-8') as f:
            br = json.load(f)
        best_combo = br.get('best_combo')
        exp = br.get('experiments', {}).get(best_combo or '', {})
        holdout = exp.get('holdout', {})
        if holdout:
            baseline_metrics = holdout
    except Exception:
        pass

    def _deep_entry(name, stats_file, w_file, v_file, label):
        path_w = os.path.join(_MODELS_DIR, w_file)
        path_v = os.path.join(_MODELS_DIR, v_file)
        if not (os.path.exists(path_w) and os.path.exists(path_v)):
            return None
        metrics = {}
        try:
            with open(os.path.join(stats_dir, stats_file),
                      'r', encoding='utf-8') as f:
                metrics = json.load(f).get('test_metrics', {})
            # 深度模型指标用 acc，统一补一个 accuracy 键，供前端/接口统一读取
            if 'accuracy' not in metrics and 'acc' in metrics:
                metrics['accuracy'] = metrics['acc']
        except Exception:
            pass
        return {'name': name, 'label': label, 'file': w_file,
                'metrics': metrics}

    available = []
    if os.path.exists(os.path.join(_MODELS_DIR, 'text_baseline.joblib')):
        available.append({
            'name': 'baseline',
            'label': TEXT_MODEL_LABELS['baseline'],
            'file': 'text_baseline.joblib',
            'metrics': baseline_metrics,
        })
    for entry in (
        _deep_entry('bilstm', 'text_bilstm_results.json',
                    'text_bilstm.pt', 'text_bilstm_vocab.json',
                    TEXT_MODEL_LABELS['bilstm']),
        _deep_entry('cnn', 'text_cnn_results.json',
                    'text_cnn.pt', 'text_cnn_vocab.json',
                    TEXT_MODEL_LABELS['cnn']),
    ):
        if entry is not None:
            available.append(entry)
    return {'modality': 'text',
            'dataset': 'Telecom_Fraud_Texts_5（电信诈骗短信）',
            'models': available,
            'default': 'ensemble'}


def main():
    try:
        if len(sys.argv) < 2:
            result = {
                "riskScore": 0,
                "riskLevel": "检测失败",
                "detail": "未提供检测文本",
                "keywords": [],
                "patterns": []
            }
            print(json.dumps(result, ensure_ascii=False))
            return

        content = sys.argv[1]
        model = sys.argv[2] if len(sys.argv) >= 3 else None
        result = analyze_text(content, model=model)
        print(json.dumps(result, ensure_ascii=False))

    except Exception as e:
        error_result = {
            "riskScore": 0,
            "riskLevel": "检测失败",
            "detail": "文本检测异常：" + str(e),
            "keywords": [],
            "patterns": []
        }
        print(json.dumps(error_result, ensure_ascii=False))


if __name__ == "__main__":
    main()
