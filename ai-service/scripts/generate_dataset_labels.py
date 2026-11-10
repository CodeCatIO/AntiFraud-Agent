#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据集分类标签统计生成器（供前端可视化）

扫描现有训练数据，生成三模态的标签分布 JSON：
  - 文本：
      manual  —— CSV category 字段的人工标注 5 类（真实标签，可直接信任）
      rule    —— 用与 anti_fraud_text.py 同源的关键词/正则规则，对诈骗文本
                  做更细的作案手法推断（刷单返利/钓鱼链接/虚假贷款…），
                  属于"规则推断"，不是人工标注，未命中归"其他诈骗"
  - 语音：真人语音 / AI合成语音
  - 图像：真实图片 / AI生成图片 / PS篡改图片

输入：
  data/text/processed/{train,val,test}.csv（列 content,label,category）
  data/voice/raw/{normal,fraud}/*、data/voice/stats/stats.json
  data/image/raw/{normal,fraud,tampered}/*、data/image/stats/stats.json
输出：
  data/dataset_labels.json   （由 Flask /api/dataset/labels 读取）

用法：
  python scripts/generate_dataset_labels.py
"""
import os
import re
import csv
import json
import glob
import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AI_SERVICE_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(AI_SERVICE_DIR, 'data')
OUT_PATH = os.path.join(DATA_DIR, 'dataset_labels.json')

EXAMPLES_PER_LABEL = 2
EXAMPLE_MAX_CHARS = 120

# ============================================================
#  文本：人工标注 category 字段的展示元数据
# ============================================================
# CSV 中 category 为 0/空 表示正常文本
MANUAL_NORMAL_KEY = '正常文本'
MANUAL_META = {
    MANUAL_NORMAL_KEY: {'risk': 0, 'desc': '普通营销/通知/日常对话等非诈骗文本'},
    '冒充公检法及政府机关类': {'risk': 1, 'desc': '假冒公安/检察/法院/政府，以涉案、清查为由恐吓'},
    '冒充领导、熟人类': {'risk': 1, 'desc': '冒充领导、老师、亲友，以急事/帮忙为由要钱'},
    '贷款、代办信用卡类': {'risk': 1, 'desc': '低息无抵押诱饵，骗保证金/解冻费/资料费'},
    '冒充客服服务': {'risk': 1, 'desc': '假冒客服/快递售后，以退款理赔诱导转账或填信息'},
}

# ============================================================
#  文本：规则细分手法
#  顺序即优先级：一条文本只归入第一个命中的手法（互斥单标签）。
#  与 anti_fraud_text.py 的关键词库/正则同源，仅做归类用途。
# ============================================================
RULE_TYPES = [
    ('冒充公检法',
     r'公安|警察|警官|检察院|法院|传票|通缉|涉案|刑事|拘捕|办案|资金清查|安全账户|监管账户'),
    ('刷单返利',
     r'刷单|刷信誉|刷销量|刷好评|返利|返佣|日赚|躺赚|足不出户|点赞.{0,6}(关注|员|任务)|做.{0,3}任务.{0,8}(佣金|返现)'),
    ('虚假投资理财',
     r'投资|理财|炒股|股票|基金|稳赚|高收益|内幕|涨停|数字货币|比特币|期货|外汇盘|带单'),
    ('虚假贷款信用卡',
     r'贷款|借款|放款|信用卡|提额|无抵押|免息|免审核|秒批|额度|征信|解冻费|保证金'),
    ('冒充客服退款理赔',
     r'客服|退款|理赔|退货|售后|会员.*(扣费|取消)|快递.{0,8}(丢|损|赔|异常)|质量问题|订单异常'),
    ('中奖补贴退税',
     r'中奖|领奖|奖金|抽奖|幸运用户|补贴|退税|免费领|红包|话费.*(领|兑)|兑换码'),
    ('求职兼职缴费',
     r'招聘|入职|上岗|培训费|押金|保证金|服装费|体检费|工本费|报名费|诚聘|急招'),
    ('冒充领导熟人',
     r'领导|书记|局长|校长|园长|院长|站长|所长|主任|主席|干部|秘书|老师|班主任|亲戚|表哥|表姐|爸爸|妈妈|老同学|换号|办公室一趟|我是你.{0,3}(朋友|领导)|帮忙.{0,8}(转账|汇款|垫付|付款)|先(帮|代).{0,4}(转账|汇款|支付|交钱)|支付定金|交.{0,2}定金'),
    ('钓鱼链接/仿冒APP',
     r'https?://|www\.|[a-z0-9-]+\.(com|cn|net|cc|top|xyz)|链接|网址|点击.{0,6}(下载|进入|打开)|扫码|二维码|下载.{0,6}(app|APP|软件|应用)'),
    ('索要验证码/敏感信息',
     r'验证码.{0,12}(告诉|发送|告知|提供|报)|身份证号?|银行卡号?|个人信息|家庭住址|人脸验证'),
]
RULE_FALLBACK = '其他诈骗手法'


def classify_rule_type(text):
    """按优先级返回第一个命中的细分手法名，未命中归兜底类。"""
    for name, pattern in RULE_TYPES:
        if re.search(pattern, text):
            return name
    return RULE_FALLBACK


def short_text(text):
    text = str(text).strip().replace('\n', ' ')
    return text[:EXAMPLE_MAX_CHARS] + ('…' if len(text) > EXAMPLE_MAX_CHARS else '')


def build_text_stats():
    csv_paths = [
        os.path.join(DATA_DIR, 'text', 'processed', f'{s}.csv')
        for s in ('train', 'val', 'test')
    ]
    csv_paths = [p for p in csv_paths if os.path.exists(p)]
    if not csv_paths:
        return None

    manual_counts = {k: 0 for k in MANUAL_META}
    rule_counts = {name: 0 for name, _ in RULE_TYPES}
    rule_counts[RULE_FALLBACK] = 0
    manual_examples = {k: [] for k in MANUAL_META}
    rule_examples = {name: [] for name, _ in RULE_TYPES}
    rule_examples[RULE_FALLBACK] = []
    split_counts = {}
    total = fraud_total = 0

    for csv_path in csv_paths:
        split = os.path.splitext(os.path.basename(csv_path))[0]
        n_split = 0
        with open(csv_path, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                content = (row.get('content') or '').strip()
                if not content:
                    continue
                label = int(row.get('label') or 0)
                category = (row.get('category') or '').strip()
                total += 1
                n_split += 1

                # 人工标注 5 类
                if label == 1 and category in MANUAL_META:
                    mkey = category
                elif label == 0:
                    mkey = MANUAL_NORMAL_KEY
                else:
                    # 理论上不会出现：标签与类别不一致时按 label 兜底
                    mkey = MANUAL_NORMAL_KEY if label == 0 else RULE_FALLBACK
                manual_counts[mkey] = manual_counts.get(mkey, 0) + 1
                if len(manual_examples[mkey]) < EXAMPLES_PER_LABEL:
                    manual_examples[mkey].append(short_text(content))

                # 仅对诈骗文本做规则细分
                if label == 1:
                    fraud_total += 1
                    rtype = classify_rule_type(content)
                    rule_counts[rtype] += 1
                    if len(rule_examples[rtype]) < EXAMPLES_PER_LABEL:
                        rule_examples[rtype].append(short_text(content))
        split_counts[split] = n_split

    manual_items = [
        {
            'name': name,
            'value': manual_counts[name],
            'risk': MANUAL_META[name]['risk'],
            'desc': MANUAL_META[name]['desc'],
            'examples': manual_examples[name],
        }
        for name in MANUAL_META
    ]
    # 规则细分类按数量降序，兜底类固定排最后
    ordered = [n for n, _ in RULE_TYPES] + [RULE_FALLBACK]
    rule_items = [
        {
            'name': name,
            'value': rule_counts[name],
            'examples': rule_examples[name],
        }
        for name in ordered if rule_counts[name] > 0 or name == RULE_FALLBACK
    ]
    covered = sum(v for k, v in rule_counts.items() if k != RULE_FALLBACK)
    coverage = round(covered / fraud_total * 100, 1) if fraud_total else 0.0

    return {
        'total': total,
        'fraudTotal': fraud_total,
        'normalTotal': total - fraud_total,
        'splits': split_counts,
        'manual': {
            'title': '人工标注类别（训练数据 category 字段）',
            'source': '训练集真实标注，可直接信任',
            'items': manual_items,
        },
        'rule': {
            'title': '诈骗手法细分（关键词规则自动推断）',
            'source': '基于关键词/正则规则对诈骗文本自动打标，非人工标注',
            'coverage': coverage,
            'items': rule_items,
        },
    }


# ============================================================
#  语音 / 图像：目录计数
# ============================================================
def count_files(sub_dir, exts):
    n = 0
    if os.path.isdir(sub_dir):
        n = sum(
            1 for f in os.listdir(sub_dir)
            if os.path.isfile(os.path.join(sub_dir, f))
            and f.lower().endswith(exts)
        )
    return n


def load_modality_stats(modality):
    path = os.path.join(DATA_DIR, modality, 'stats', 'stats.json')
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None
    return None


def build_voice_stats():
    raw = os.path.join(DATA_DIR, 'voice', 'raw')
    normal = count_files(os.path.join(raw, 'normal'), ('.wav', '.mp3', '.flac'))
    fraud = count_files(os.path.join(raw, 'fraud'), ('.wav', '.mp3', '.flac'))
    stats = load_modality_stats('voice') or {}
    duration_min = None
    if stats.get('total_duration_sec'):
        duration_min = round(stats['total_duration_sec'] / 60, 1)
    return {
        'total': normal + fraud,
        'durationMin': duration_min,
        'augmentedTotal': stats.get('total_with_augmentation'),
        'items': [
            {
                'name': '真人语音', 'key': 'normal', 'value': normal,
                'desc': '真实人类说话录音（YouTube 真人讲话）',
            },
            {
                'name': 'AI合成语音', 'key': 'fraud', 'value': fraud,
                'desc': 'TTS 机器合成语音（ElevenLabs），伪造类正样本',
            },
        ],
    }


def build_image_stats():
    raw = os.path.join(DATA_DIR, 'image', 'raw')
    normal = count_files(os.path.join(raw, 'normal'),
                         ('.png', '.jpg', '.jpeg', '.bmp'))
    fraud = count_files(os.path.join(raw, 'fraud'),
                        ('.png', '.jpg', '.jpeg', '.bmp'))
    tampered = count_files(os.path.join(raw, 'tampered'),
                           ('.png', '.jpg', '.jpeg', '.bmp'))
    stats = load_modality_stats('image') or {}
    return {
        'total': normal + fraud + tampered,
        'augmentedTotal': stats.get('total_with_augmentation'),
        'items': [
            {
                'name': '真实图片', 'key': 'normal', 'value': normal,
                'desc': '真实拍摄、未经篡改的照片',
            },
            {
                'name': 'AI生成图片', 'key': 'fraud', 'value': fraud,
                'desc': '扩散模型/GAN 生成的 AI 艺术图',
            },
            {
                'name': 'PS篡改图片', 'key': 'tampered', 'value': tampered,
                'desc': '真实照片被局部编辑拼接（IMD2020 源下载中，当前为 0）',
            },
        ],
    }


def main():
    print('=' * 60)
    print('生成数据集分类标签统计')
    print('=' * 60)

    text = build_text_stats()
    voice = build_voice_stats()
    image = build_image_stats()

    payload = {
        'generatedAt': datetime.datetime.now().isoformat(timespec='seconds'),
        'text': text,
        'voice': voice,
        'image': image,
    }
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    if text:
        print(f"\n文本 共 {text['total']} 条（诈骗 {text['fraudTotal']}）")
        print('  人工标注:')
        for it in text['manual']['items']:
            print(f"    {it['name']:<22} {it['value']}")
        print(f"  规则细分（覆盖率 {text['rule']['coverage']}%）:")
        for it in text['rule']['items']:
            print(f"    {it['name']:<22} {it['value']}")
    print(f"\n语音: {voice['items'][0]['value']} 真人 / "
          f"{voice['items'][1]['value']} AI合成")
    print(f"图像: {image['items'][0]['value']} 真实 / "
          f"{image['items'][1]['value']} AI生成 / "
          f"{image['items'][2]['value']} PS篡改")
    print(f"\n已写出 -> {OUT_PATH}")


if __name__ == '__main__':
    main()
