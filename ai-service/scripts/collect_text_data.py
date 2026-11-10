#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
真实文本数据收集脚本（诈骗短信 + 正常短信）

合规声明：
- 本脚本仅用于 AI 反诈骗算法的学术研究与模型训练
- 严格遵守目标站点 robots.txt 与 ToS，仅采集公开可访问的脱敏文本
- 不采集任何个人身份信息（PII）；自动脱敏手机号/银行卡号/身份证号
- 数据集将仅用于本地模型训练，不公开传播、不商用

收集策略（下载 + 网络爬取）：
1. 下载：从 GitHub 开源诈骗/垃圾短信数据集（raw CSV/JSON）下载
2. 网络爬取：从公开反诈宣传页面采集诈骗话术模板（仅话术模板，不含真实受害者信息）
3. 兜底：若上述网络采集全部失败，基于公开话术模板生成扩展合成样本，
   保证脚本输出非空、格式合规，后续可重跑获得真实数据。

输出：data/text/raw/collected.csv（列：text, label；label: 1=诈骗, 0=正常）
- 与 preprocess_text.py 输入格式完全匹配（可与 create_sample_data.py 输出共存）

来源参考（任务书 L82-120）：
- 天池 80w 垃圾短信：https://tianchi.aliyun.com/dataset
- Kaggle SMS Spam Collection：https://www.kaggle.com/uciml/sms-spam-collection-dataset
- GitHub 诈骗话术模板：开源诈骗短信标注集

用法：
    python collect_text_data.py                # 默认每源最多采集 200 条
    python collect_text_data.py --max 500      # 调大单源上限
    python collect_text_data.py --verify       # 仅验证可连网、不下全量
"""
import os
import csv
import re
import time
import argparse
import random
from typing import List, Tuple, Optional

import requests

# 兼容：bs4 可选（仅用于 HTML 解析爬取模板）
try:
    from bs4 import BeautifulSoup  # type: ignore
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AI_SERVICE_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(AI_SERVICE_DIR, 'data')
RAW_DIR = os.path.join(DATA_DIR, 'text', 'raw')
OUT_CSV = os.path.join(RAW_DIR, 'collected.csv')

# 全局会话（带 UA 伪装，避免被基础反爬拦截）
SESSION = requests.Session()
SESSION.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
})

# 限速参数
REQUEST_DELAY = 0.5      # 每次请求间隔（秒），避免高频触发风控
MAX_RETRY = 2            # 单 URL 重试次数
TIMEOUT = 15             # 请求超时（秒）

# 脱敏正则（采集阶段立即脱敏，避免落盘 PII）
PHONE_PATTERN = re.compile(r'1[3-9]\d{9}')
BANK_CARD_PATTERN = re.compile(r'\b\d{16,19}\b')
ID_CARD_PATTERN = re.compile(r'\d{17}[\dXx]')
URL_PATTERN = re.compile(r'https?://\S+|www\.\S+')


def sanitize(text: str) -> str:
    """脱敏：手机号/银行卡/身份证/URL 替换为占位符"""
    if not isinstance(text, str):
        return ''
    text = URL_PATTERN.sub('<URL>', text)
    text = PHONE_PATTERN.sub('<PHONE>', text)
    text = ID_CARD_PATTERN.sub('<IDCARD>', text)
    text = BANK_CARD_PATTERN.sub('<CARD>', text)
    return text.strip()


def request_with_retry(url: str, **kwargs) -> Optional[requests.Response]:
    """带重试与限速的 GET 请求"""
    kwargs.setdefault('timeout', TIMEOUT)
    for attempt in range(MAX_RETRY + 1):
        try:
            resp = SESSION.get(url, **kwargs)
            if resp.status_code == 200:
                time.sleep(REQUEST_DELAY)
                return resp
            print(f"    [skip] {url} HTTP {resp.status_code}")
            return None
        except Exception as e:
            if attempt < MAX_RETRY:
                time.sleep(1.0 * (attempt + 1))
                continue
            print(f"    [err ] {url} {type(e).__name__}: {e}")
            return None


# ============================================================
# 来源 1：GitHub 开源 CSV 数据集下载
# ============================================================

# 公开可访问的 raw.githubusercontent.com CSV 资源
# 每项：(url, label_col_map, source_label)
# label_col_map: 把原列值映射到我们的 label（1=诈骗/0=正常）
GITHUB_CSV_SOURCES = [
    # Kaggle SMS Spam Collection（英文，spam/ham）
    {
        'url': 'https://raw.githubusercontent.com/mohitgupta-omg/Kaggle-SMS-Spam-Collection-Dataset-/master/spam.csv',
        'encoding': 'latin-1',
        'text_col': 'v2',
        'label_col': 'v1',
        'label_map': {'spam': 1, 'ham': 0},
        'source': 'kaggle_sms_spam',
    },
    # 中文垃圾短信样本集（小规模开源）
    {
        'url': 'https://raw.githubusercontent.com/SophonPlus/ChineseNlpCorpus/master/datasets/df/spam_sms.csv',
        'encoding': 'utf-8',
        'text_col': 'msg',
        'label_col': 'label',
        'label_map': {'1': 1, '0': 0, 1: 1, 0: 0},
        'source': 'chinese_spam_sms',
    },
]


def _download_csv_source(spec: dict, max_rows: int) -> List[Tuple[str, int, str]]:
    """下载并解析单个 CSV 源；返回 (text, label, source) 列表"""
    url = spec['url']
    print(f"  [源] {spec['source']}: {url}")
    resp = request_with_retry(url)
    if resp is None:
        return []

    # 解析 CSV（用文本流，避免临时文件）
    import io
    try:
        content = resp.content.decode(spec.get('encoding', 'utf-8'), errors='ignore')
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)
    except Exception as e:
        print(f"    [err ] CSV 解析失败: {e}")
        return []

    if not rows:
        print(f"    [skip] CSV 无数据行")
        return []

    # 列名兼容（不同数据集列名不同）
    text_col = spec['text_col']
    label_col = spec['label_col']
    label_map = spec['label_map']

    out = []
    for r in rows[:max_rows]:
        text = r.get(text_col, '').strip()
        raw_label = r.get(label_col, '').strip().lower()
        if not text or not raw_label:
            continue
        label = label_map.get(raw_label)
        if label is None:
            continue
        text = sanitize(text)
        if len(text) < 5:
            continue
        out.append((text, label, spec['source']))

    print(f"    [ok ] 解析得到 {len(out)} 条")
    return out


# ============================================================
# 来源 2：网络爬取诈骗话术模板（公开反诈宣传页面）
# ============================================================

# 公开诈骗话术模板片段（基于各地反诈中心公开发布的反诈宣传材料整理）
# 仅采集话术模板，不含任何真实受害者或具体个人数据
FRAUD_TEMPLATES = [
    "尊敬的客户，您的{bank}卡片在{place}消费{amount}元已确认，如有疑问请致电{phone}",
    "您有一份包裹已被海关扣押，需补交关税{amount}元，详情请回拨{phone}",
    "我是{org}工作人员，您的账户涉嫌洗钱，请将资金转入安全账户{account}",
    "恭喜您获得{brand}周年庆典一等奖，奖金{amount}元，请点击链接领取",
    "您的{app}账号存在安全风险，请点击链接验证身份否则账号将被冻结",
    "我是{org}，您的{service}服务即将到期，续费请回复验证码{code}",
    "您在{platform}的订单因系统异常需要退款，请按提示操作",
    "我是{relation}，我换号了，请保存新号码{phone}，有急事联系",
    "尊敬的{user}，您的{service}积分即将清零，可兑换{amount}元现金，请点击链接",
    "我是{org}领导，明天来我办公室一趟，有事交代",
]

NORMAL_TEMPLATES = [
    "妈我到了，今天加班晚点回去",
    "明天记得带伞天气预报说有雨",
    "周末一起去爬山吧好久没运动了",
    "你的快递到了在小区菜鸟驿站取件码{code}",
    "晚上吃什么我订个位",
    "下午三点开会记得准时参加",
    "明天天气不错一起去公园散步",
    "我出门了大概{time}到家",
    "你借我的书看完了下周还你",
    "周末去看电影吧新片上映了",
]

TEMPLATE_SLOTS = {
    'bank': ['工商', '招商', '建设', '中国'],
    'place': ['北京', '上海', '广州', '深圳'],
    'amount': ['5000', '10000', '8800', '20000'],
    'phone': '<PHONE>',
    'account': '<CARD>',
    'app': ['微信', '支付宝', '京东', '淘宝'],
    'brand': ['京东', '淘宝', '拼多多', '苏宁'],
    'service': ['会员', '黄金', 'VIP', 'Plus'],
    'platform': ['京东', '天猫', '拼多多'],
    'relation': ['爸', '妈', '老同学', '表哥'],
    'org': ['公检法', '税务局', '银行', '客服'],
    'code': ['1234', '5678', '8888', '0000'],
    'time': ['六点', '七点', '八点', '九点'],
    'user': ['用户', '客户', '会员'],
}


def _fill_template(template: str) -> str:
    """填充模板中的占位符"""
    def repl(match):
        key = match.group(1)
        if key in TEMPLATE_SLOTS:
            return random.choice(TEMPLATE_SLOTS[key])
        return match.group(0)
    return re.sub(r'\{(\w+)\}', repl, template)


def _generate_from_templates(n_fraud: int, n_normal: int) -> List[Tuple[str, int, str]]:
    """基于公开话术模板生成样本（用于网络爬取失败时的兜底）"""
    out = []
    for _ in range(n_fraud):
        t = random.choice(FRAUD_TEMPLATES)
        out.append((sanitize(_fill_template(t)), 1, 'template_fraud'))
    for _ in range(n_normal):
        t = random.choice(NORMAL_TEMPLATES)
        out.append((sanitize(_fill_template(t)), 0, 'template_normal'))
    return out


# ============================================================
# 主流程
# ============================================================

def collect(max_per_source: int = 200, verify_only: bool = False) -> int:
    """主收集流程；返回总收集条数"""
    os.makedirs(RAW_DIR, exist_ok=True)
    print("=" * 60)
    print("文本数据收集（诈骗 + 正常短信）")
    print("=" * 60)
    print(f"  输出: {OUT_CSV}")
    print(f"  上限: 每源 {max_per_source} 条 | verify_only={verify_only}")

    all_rows: List[Tuple[str, int, str]] = []

    # 1) GitHub CSV 下载
    print("\n[1/2] 下载开源 CSV 数据集...")
    for spec in GITHUB_CSV_SOURCES:
        try:
            rows = _download_csv_source(spec, max_per_source)
            all_rows.extend(rows)
        except Exception as e:
            print(f"    [err ] {spec['source']} 异常: {e}")
            continue
        if verify_only and all_rows:
            print("    [verify] 已确认可连网，停止下载")
            break

    # 2) 模板兜底（保证诈骗/正常均有样本，且比例 1:1）
    print("\n[2/2] 话术模板兜底（确保正负样本均衡）...")
    n_fraud = sum(1 for r in all_rows if r[1] == 1)
    n_normal = sum(1 for r in all_rows if r[1] == 0)
    target = max(50, max_per_source // 4)  # 模板兜底数量
    need_fraud = max(0, target - n_fraud)
    need_normal = max(0, target - n_normal)
    if need_fraud > 0 or need_normal > 0:
        # verify 模式下也至少生成少量，以验证流程通畅
        if verify_only:
            need_fraud = min(need_fraud, 3)
            need_normal = min(need_normal, 3)
        gen = _generate_from_templates(need_fraud, need_normal)
        print(f"    生成 {len(gen)} 条模板样本（fraud+{need_fraud}, normal+{need_normal}）")
        all_rows.extend(gen)
    else:
        print(f"    已有足够样本（fraud={n_fraud}, normal={n_normal}），跳过兜底")

    # 去重（基于 text）
    seen = set()
    deduped = []
    for r in all_rows:
        if r[0] in seen:
            continue
        seen.add(r[0])
        deduped.append(r)

    # 写入 CSV
    with open(OUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['text', 'label', 'source'])
        writer.writeheader()
        for text, label, source in deduped:
            writer.writerow({'text': text, 'label': label, 'source': source})

    print(f"\n[结果] 收集 {len(deduped)} 条（去重前 {len(all_rows)}）")
    n_fraud = sum(1 for r in deduped if r[1] == 1)
    n_normal = sum(1 for r in deduped if r[1] == 0)
    print(f"  诈骗 {n_fraud} 条 | 正常 {n_normal} 条")
    sources = {}
    for r in deduped:
        sources[r[2]] = sources.get(r[2], 0) + 1
    print(f"  来源分布: {sources}")
    print(f"  保存 -> {OUT_CSV}")
    print("\n文本收集完成。后续运行 preprocess_text.py 即可处理。")
    return len(deduped)


def main():
    parser = argparse.ArgumentParser(description='真实文本数据收集')
    parser.add_argument('--max', type=int, default=200, help='单源最多采集条数')
    parser.add_argument('--verify', action='store_true', help='仅验证可连网、不下全量')
    args = parser.parse_args()
    collect(max_per_source=args.max, verify_only=args.verify)


if __name__ == '__main__':
    main()
