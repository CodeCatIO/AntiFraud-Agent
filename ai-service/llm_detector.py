#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
LLM 语义检测层 (llm_detector.py)

调用 DeepSeek Chat API（OpenAI 兼容协议）对文本做语义级诈骗分析，
作为规则层 + 本地模型层之上的第三层检测：

  - 语义理解：没见过的新话术也能判断（规则层只认已知模式）
  - 结构化输出：riskScore / riskLevel / fraudType / reasons
  - 可选层：无 API key、断网、超时、解析失败时返回 None，
    调用方自动降级到规则层 + 本地模型层，系统不会瘫痪

配置（读取项目根目录 .env，已被 .gitignore 忽略）：
  DEEPSEEK_API_KEY     必填，DeepSeek 平台申请
  DEEPSEEK_BASE_URL    默认 https://api.deepseek.com
  DEEPSEEK_MODEL       默认 deepseek-chat
  LLM_ENABLED          设为 false 可整体关闭本层
  LLM_TIMEOUT_SECONDS  默认 20 秒
"""

import os
import json
import logging
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# .env 加载：从本文件所在目录向上逐级查找，找到即停（不覆盖已有环境变量）
# ---------------------------------------------------------------------------
def _load_env():
    here = os.path.dirname(os.path.abspath(__file__))
    for _ in range(3):
        candidate = os.path.join(here, '.env')
        if os.path.exists(candidate):
            try:
                with open(candidate, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#') or '=' not in line:
                            continue
                        key, val = line.split('=', 1)
                        key = key.strip()
                        val = val.strip().strip('"').strip("'")
                        os.environ.setdefault(key, val)
            except Exception:
                pass
            break
        here = os.path.dirname(here)

_load_env()

_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
_BASE_URL = (os.environ.get('DEEPSEEK_BASE_URL') or 'https://api.deepseek.com').rstrip('/')
_MODEL = os.environ.get('DEEPSEEK_MODEL') or 'deepseek-chat'
_ENABLED = os.environ.get('LLM_ENABLED', 'true').lower() != 'false'
_TIMEOUT = float(os.environ.get('LLM_TIMEOUT_SECONDS', '20'))

# ---------------------------------------------------------------------------
# Prompt：让模型扮演反诈专家，只输出 JSON
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """你是国家反诈中心的诈骗文本检测专家。分析用户输入的短信/聊天内容是否为诈骗。

常见诈骗类型（供参考，不限于此）：
1. 冒充公检法：声称涉案，要求转账到"安全账户"
2. 刷单返利：先小额返利骗信任，再诱导大额垫付
3. 虚假投资理财：稳赚不赔、高额回报、内幕消息
4. 冒充客服退款/理赔：索要验证码、银行卡信息
5. 冒充公检法/熟人借钱：冒充领导、亲友紧急借钱
6. 虚假贷款：低息无抵押，先交保证金/解冻费
7. 求职招聘缴费：入职前收培训费/押金/服装费（正规单位不收费）
8. 中奖/补贴诈骗：中奖了/领补贴，先交手续费或填身份信息
9. 冒充政府养老/福利：免费养老、高额补贴，诱导填身份证银行卡
10. 钓鱼链接：仿冒官方短信诱导点击链接

判断要点：
- 任何"先交钱再办事"都是诈骗
- 索要验证码、密码、银行卡号=诈骗
- 高收益承诺=诈骗
- 正规机构不会通过私人聊天办理业务
- 正常生活对话（家人聊天、快递通知、工作沟通）为无风险

只输出如下 JSON，不要输出任何其他内容：
{"riskScore": 0到100的整数, "riskLevel": "高风险/中风险/低风险/无风险", "fraudType": "诈骗类型或null", "reasons": ["判断理由1", "理由2"]}"""

FEW_SHOT = [
    {"role": "user", "content": "我们养老院可以免费接收老人抚养，请填写身份相关信息"},
    {"role": "assistant", "content": json.dumps({"riskScore": 90, "riskLevel": "高风险", "fraudType": "养老福利骗局/个人信息收集", "reasons": ["以免费照护为诱饵", "诱导填写身份信息，正规机构不需要通过聊天收集"]}, ensure_ascii=False)},
    {"role": "user", "content": "亲，你昨天订的奶茶已出货，预计明天送达，请保持电话畅通"},
    {"role": "assistant", "content": json.dumps({"riskScore": 5, "riskLevel": "低风险", "fraudType": None, "reasons": ["正常快递通知，无索要钱财或敏感信息行为"]}, ensure_ascii=False)},
]


def _chat_api(content):
    """调用 DeepSeek Chat API，返回模型文本输出。失败抛异常由上层处理。"""
    url = _BASE_URL + '/chat/completions'
    payload = {
        "model": _MODEL,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + FEW_SHOT + [
            {"role": "user", "content": content}
        ],
        "temperature": 0.1,
        "max_tokens": 300,
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + _API_KEY,
        },
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    return data['choices'][0]['message']['content']


def _parse_verdict(text):
    """从模型输出中提取 JSON 并转成与规则层兼容的结果 dict。"""
    # 模型偶尔会在 JSON 外带说明文字，取第一个 {...} 块
    start = text.find('{')
    end = text.rfind('}')
    if start < 0 or end <= start:
        raise ValueError('no JSON in LLM output')
    obj = json.loads(text[start:end + 1])

    score = max(0, min(100, int(obj.get('riskScore', 0))))
    level = obj.get('riskLevel') or ('高风险' if score >= 70 else '中风险' if score >= 40 else '低风险')
    fraud_type = obj.get('fraudType')
    reasons = obj.get('reasons') or []

    detail_parts = []
    if fraud_type:
        detail_parts.append("LLM判定类型：" + str(fraud_type))
    if reasons:
        detail_parts.append("；".join(str(r) for r in reasons[:3]))
    if not detail_parts:
        detail_parts.append("LLM语义分析未发现明显诈骗特征")

    return {
        "riskScore": score,
        "riskLevel": level,
        "detail": "LLM语义分析——" + "；".join(detail_parts),
        "keywords": [],
        "patterns": [],
        "llm": True,
    }


def analyze_text_llm(content):
    """LLM 语义层入口。任何失败返回 None（调用方降级），绝不抛异常影响主流程。"""
    if not _ENABLED or not _API_KEY:
        logger.warning("LLM layer skipped: DEEPSEEK_API_KEY missing or LLM_ENABLED=false")
        return None
    if not content or not content.strip():
        return None
    try:
        raw = _chat_api(content[:2000])  # 截断防超长
        return _parse_verdict(raw)
    except Exception as e:
        logger.warning(f"LLM layer degraded: {type(e).__name__}: {e}")
        return None


def is_enabled():
    """供健康检查使用：LLM 层是否可用。"""
    return _ENABLED and bool(_API_KEY)
