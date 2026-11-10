#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
多模态对齐案例集生成脚本（任务7 前置数据）

现有文本/语音/图像数据互不对齐，无法做同案例级融合。本脚本生成
"一个案例同时含文本+语音+图像"的对齐数据集，并刻意注入模态级信号缺失：
每个模态以 25% 概率退化为中性/不可信样本（模拟实际场景中该模态无有效
证据，如短信内容中性、通话听不清、截图为普通风景照）。

生成规则：
  - 标签：fraud(1) / normal(0)，各 N_CASES_PER_CLASS 个
  - 文本：诈骗话术模板 / 日常对话模板 / 中性模板（不可信模态）
  - 语音：低频正弦+噪声（诈骗）/ 高频正弦（正常）/ 中频重噪声（不可信）
  - 图像：红粉渐变（诈骗截图）/ 绿蓝渐变（正常）/ 灰色噪声（不可信）

输出：
  data/multimodal/cases/case_XXXX/{text.txt, voice.wav, image.png}
  data/multimodal/cases/labels.csv（case_id, label, ambiguous_t/v/i）

效果预期：单模态约 75% 有效 → 单模态准确率约 75%；
三模态同时不可信概率 0.25^3≈1.6% → 融合可显著提升。
真实场景下接入对齐的真实报案数据后重跑即可。
"""
import os
import csv
import json

import numpy as np
from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AI_SERVICE_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(AI_SERVICE_DIR, 'data')
CASES_DIR = os.path.join(DATA_DIR, 'multimodal', 'cases')

SR = 16000
DURATION = 2.0
IMG_SIZE = 224
N_CASES_PER_CLASS = 60
AMBIGUOUS_PROB = 0.25
RANDOM_STATE = 42


# ============================================================
#  文本模板
# ============================================================

FRAUD_TEXT_TEMPLATES = [
    "恭喜您获得{brand}购物节抽奖一等奖，奖金{amount}元，请点击链接 {url} 领取，验证码{code}",
    "尊敬的用户，您的账户存在异常，请立即拨打{phone}联系客服解冻，否则将永久冻结",
    "您好，我是{gov}工作人员，您有一笔退税{amount}元未领取，请提供银行卡号和身份证信息核实",
    "您的快递丢失，我们将进行三倍赔偿，请添加微信客服 {wxid} 处理",
    "恭喜中奖！您被抽中为幸运用户，扫码下载APP即可领取{prize}一台，名额有限",
    "我是{police}民警，你涉嫌一起洗钱案件，请将资金转入安全账户接受调查，电话{phone}",
    "您的银行卡将被扣除年费{amount}元，详情请咨询{phone}，逾期影响个人征信",
    "您的孩子在学校突发急病需紧急手术，请立刻转账{amount}元到医院账户{card}",
]

NORMAL_TEXT_TEMPLATES = [
    "妈，我到家了，今天加班到九点，累死了",
    "明天天气预报说有雨，记得带伞",
    "周末一起去爬山吧，好久没运动了",
    "你的快递到了，放在小区菜鸟驿站，取件码{code}",
    "晚上吃什么？我想吃火锅，你定个位吧",
    "我在楼下便利店，要不要帮你带瓶水",
    "会议改到下午三点了，在二楼会议室，记得带上周报",
    "刚跑完步，公园人还挺多的，你要不要也出来走走",
]

# 中性文本：无诈骗/日常强特征，标签不可判（不可信模态）
NEUTRAL_TEXT_TEMPLATES = [
    "好的，知道了",
    "嗯嗯，可以",
    "行，没问题",
    "今天天气还行",
    "收到",
    "稍等一下",
    "这个再说吧",
    "好的好的",
]

FILL = {
    'brand': ['京东', '天猫', '淘宝', '苏宁'],
    'amount': ['80000', '100000', '50000', '200000', '30000'],
    'url': ['http://t.cn/abc123', 'http://x.ly/fraud', 'http://95588-x.cn'],
    'code': ['8888', '1234', '6688', '0001'],
    'phone': ['13800138000', '13599558866', '021-88889999'],
    'gov': ['税务局', '社保局', '财政局'],
    'wxid': ['kefu886', 'service001', 'peichang66'],
    'prize': ['iPhone15', '华为Mate60', '平板电脑'],
    'police': ['市公安局', '刑侦大队'],
    'card': ['6222 0000 1111 2222', '6228 8888 6666 5555'],
}


def render(template, rng):
    """简单槽位填充"""
    s = template
    while '{' in s:
        a = s.index('{')
        b = s.index('}', a)
        key = s[a + 1:b]
        val = str(rng.choice(FILL[key]))
        s = s[:a] + val + s[b + 1:]
    return s


# ============================================================
#  语音合成
# ============================================================

def synth_fraud_voice(rng):
    """低频 140-230Hz + 噪声（对应 create_sample_data 的诈骗特征）"""
    t = np.linspace(0, DURATION, int(SR * DURATION), endpoint=False)
    freq = rng.uniform(140, 230)
    y = 0.5 * np.sin(2 * np.pi * freq * t)
    y += rng.uniform(0.03, 0.08) * rng.randn(len(t))
    return y


def synth_normal_voice(rng):
    """高频 380-500Hz（对应正常特征）"""
    t = np.linspace(0, DURATION, int(SR * DURATION), endpoint=False)
    freq = rng.uniform(380, 500)
    y = 0.5 * np.sin(2 * np.pi * freq * t)
    return y


def synth_ambiguous_voice(rng):
    """中频 280-340Hz + 重噪声（无法辨别）"""
    t = np.linspace(0, DURATION, int(SR * DURATION), endpoint=False)
    freq = rng.uniform(280, 340)
    y = 0.3 * np.sin(2 * np.pi * freq * t)
    y += rng.uniform(0.15, 0.3) * rng.randn(len(t))
    return y


def save_wav(path, y):
    import soundfile as sf
    sf.write(path, y.astype(np.float32), SR)


# ============================================================
#  图像合成
# ============================================================

def synth_fraud_image(rng):
    """红粉色调渐变（诈骗截图风格）"""
    x = np.linspace(0, 1, IMG_SIZE)
    r = (rng.uniform(170, 220) + 0 * x)
    g = rng.uniform(30, 80) + x * rng.uniform(10, 40)
    b = rng.uniform(40, 90) + x * rng.uniform(10, 40)
    img = np.zeros((IMG_SIZE, IMG_SIZE, 3))
    img[:, :, 0] = r[None, :]
    img[:, :, 1] = g[None, :]
    img[:, :, 2] = b[None, :]
    img += rng.randint(-8, 9, img.shape)
    return np.clip(img, 0, 255).astype(np.uint8)


def synth_normal_image(rng):
    """绿蓝色调渐变（正常图片风格）"""
    x = np.linspace(0, 1, IMG_SIZE)
    r = rng.uniform(30, 80) + x * rng.uniform(10, 40)
    g = rng.uniform(170, 220) + 0 * x
    b = rng.uniform(120, 200) + x * rng.uniform(10, 40)
    img = np.zeros((IMG_SIZE, IMG_SIZE, 3))
    img[:, :, 0] = r[None, :]
    img[:, :, 1] = g[None, :]
    img[:, :, 2] = b[None, :]
    img += rng.randint(-8, 9, img.shape)
    return np.clip(img, 0, 255).astype(np.uint8)


def synth_ambiguous_image(rng):
    """灰色噪声图（无类别信息）"""
    base = rng.randint(100, 156, 3)[None, None, :]
    img = np.broadcast_to(base, (IMG_SIZE, IMG_SIZE, 3)).copy()
    img += rng.randint(-40, 41, img.shape)
    return np.clip(img, 0, 255).astype(np.uint8)


def save_image(path, img):
    Image.fromarray(img, mode='RGB').save(path)


# ============================================================
#  主流程
# ============================================================

def main():
    rng = np.random.RandomState(RANDOM_STATE)

    print("=" * 60)
    print("生成多模态对齐案例集")
    print("=" * 60)

    os.makedirs(CASES_DIR, exist_ok=True)

    labels = []
    case_idx = 0
    stats = {'ambiguous_t': 0, 'ambiguous_v': 0, 'ambiguous_i': 0,
             'all_ambiguous': 0}

    for label in (1, 0):
        for _ in range(N_CASES_PER_CLASS):
            case_id = f"case_{case_idx:04d}"
            case_dir = os.path.join(CASES_DIR, case_id)
            os.makedirs(case_dir, exist_ok=True)

            # 各模态独立决定是否不可信
            amb_t = rng.rand() < AMBIGUOUS_PROB
            amb_v = rng.rand() < AMBIGUOUS_PROB
            amb_i = rng.rand() < AMBIGUOUS_PROB

            # --- 文本 ---
            if amb_t:
                text = str(rng.choice(NEUTRAL_TEXT_TEMPLATES))
            elif label == 1:
                text = render(str(rng.choice(FRAUD_TEXT_TEMPLATES)), rng)
            else:
                text = render(str(rng.choice(NORMAL_TEXT_TEMPLATES)), rng)
            with open(os.path.join(case_dir, 'text.txt'), 'w',
                      encoding='utf-8') as f:
                f.write(text)

            # --- 语音 ---
            if amb_v:
                y = synth_ambiguous_voice(rng)
            elif label == 1:
                y = synth_fraud_voice(rng)
            else:
                y = synth_normal_voice(rng)
            save_wav(os.path.join(case_dir, 'voice.wav'), y)

            # --- 图像 ---
            if amb_i:
                img = synth_ambiguous_image(rng)
            elif label == 1:
                img = synth_fraud_image(rng)
            else:
                img = synth_normal_image(rng)
            save_image(os.path.join(case_dir, 'image.png'), img)

            labels.append({
                'case_id': case_id,
                'label': label,
                'ambiguous_t': int(amb_t),
                'ambiguous_v': int(amb_v),
                'ambiguous_i': int(amb_i),
            })

            stats['ambiguous_t'] += int(amb_t)
            stats['ambiguous_v'] += int(amb_v)
            stats['ambiguous_i'] += int(amb_i)
            stats['all_ambiguous'] += int(amb_t and amb_v and amb_i)
            case_idx += 1

    # labels.csv
    csv_path = os.path.join(CASES_DIR, 'labels.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'case_id', 'label', 'ambiguous_t', 'ambiguous_v',
            'ambiguous_i'])
        writer.writeheader()
        writer.writerows(labels)

    total = case_idx
    print(f"  生成 {total} 个案例（诈骗 {N_CASES_PER_CLASS} / "
          f"正常 {N_CASES_PER_CLASS}）")
    print(f"  不可信模态计数：文本 {stats['ambiguous_t']}, "
          f"语音 {stats['ambiguous_v']}, 图像 {stats['ambiguous_i']}")
    print(f"  三模态同时不可信：{stats['all_ambiguous']} 个")
    print(f"  -> {CASES_DIR}")
    print(f"  -> {csv_path}")

    # 简要元数据
    meta_path = os.path.join(DATA_DIR, 'multimodal', 'dataset_meta.json')
    os.makedirs(os.path.dirname(meta_path), exist_ok=True)
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump({
            'total_cases': total,
            'per_class': N_CASES_PER_CLASS,
            'ambiguous_probability_per_modality': AMBIGUOUS_PROB,
            'ambiguous_counts': stats,
        }, f, ensure_ascii=False, indent=2)
    print(f"  -> {meta_path}")
    print("\n案例集生成完成，可运行 train_fusion_model.py 训练融合模型。")


if __name__ == '__main__':
    main()
