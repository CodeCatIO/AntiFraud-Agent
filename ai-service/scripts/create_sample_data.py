#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
生成小规模合成数据，用于验证预处理脚本可复现性。
不依赖真实大数据集，生成：
- 10条文本（5诈骗+5正常）→ data/text/raw/sample.csv
- 3个正弦波wav（2秒/16kHz）→ data/voice/raw/{fraud,normal}/
- 6张渐变图片（100×100 PNG）→ data/image/raw/{fraud,normal,tampered}/
"""
import os
import csv
import numpy as np
from scipy.io import wavfile
from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AI_SERVICE_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(AI_SERVICE_DIR, 'data')

# 文本样本
FRAUD_TEXTS = [
    "恭喜您获得京东购物节抽奖一等奖，奖金100000元，请点击链接 http://fraud.example.com 领取，验证码8888",
    "尊敬的用户，您的账户存在异常，请立即拨打13800138000联系客服解冻，否则将永久冻结",
    "您好，我是税务局工作人员，您有一笔退税未领取，请提供银行卡号和身份证信息进行核实",
    "您的快递丢失，我们将进行三倍赔偿，请添加微信客服微信：fraud123 处理",
    "恭喜中奖！您被抽中为幸运用户，扫码下载APP即可领取iPhone15一台，活动名额有限",
]

NORMAL_TEXTS = [
    "妈，我到家了，今天加班到九点，累死了",
    "明天天气预报说有雨，记得带伞",
    "周末一起去爬山吧，好久没运动了",
    "你的快递到了，放在小区菜鸟驿站，取件码1234",
    "晚上吃什么？我想吃火锅，你定个位吧",
]


def create_text_data():
    """生成文本样本CSV"""
    raw_dir = os.path.join(DATA_DIR, 'text', 'raw')
    os.makedirs(raw_dir, exist_ok=True)
    csv_path = os.path.join(raw_dir, 'sample.csv')

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['text', 'label'])
        writer.writeheader()
        for text in FRAUD_TEXTS:
            writer.writerow({'text': text, 'label': 1})
        for text in NORMAL_TEXTS:
            writer.writerow({'text': text, 'label': 0})

    total = len(FRAUD_TEXTS) + len(NORMAL_TEXTS)
    print(f"[文本] 生成 {total} 条样本 -> {csv_path}")


def create_voice_data():
    """生成语音样本wav"""
    sr = 16000  # 采样率
    duration = 2.0  # 2秒
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)

    # 诈骗语音（2个）：不同频率的正弦波 + 噪声
    fraud_dir = os.path.join(DATA_DIR, 'voice', 'raw', 'fraud')
    os.makedirs(fraud_dir, exist_ok=True)

    y1 = 0.5 * np.sin(2 * np.pi * 200 * t) + 0.1 * np.random.randn(len(t))
    wavfile.write(os.path.join(fraud_dir, 'fraud_001.wav'), sr, (y1 * 32767).astype(np.int16))

    y2 = 0.5 * np.sin(2 * np.pi * 150 * t) + 0.15 * np.random.randn(len(t))
    wavfile.write(os.path.join(fraud_dir, 'fraud_002.wav'), sr, (y2 * 32767).astype(np.int16))

    # 正常语音（1个）：较高频率
    normal_dir = os.path.join(DATA_DIR, 'voice', 'raw', 'normal')
    os.makedirs(normal_dir, exist_ok=True)

    y3 = 0.5 * np.sin(2 * np.pi * 440 * t)
    wavfile.write(os.path.join(normal_dir, 'normal_001.wav'), sr, (y3 * 32767).astype(np.int16))

    print(f"[语音] 生成 3 个wav -> fraud/2, normal/1")


def create_image_data():
    """生成图像样本"""
    size = 100  # 100x100

    def make_gradient(color1, color2, name, save_dir):
        """生成渐变图片"""
        os.makedirs(save_dir, exist_ok=True)
        img = Image.new('RGB', (size, size))
        pixels = img.load()
        for x in range(size):
            for y in range(size):
                r = int(color1[0] + (color2[0] - color1[0]) * x / size)
                g = int(color1[1] + (color2[1] - color1[1]) * y / size)
                b = int(color1[2] + (color2[2] - color1[2]) * (x + y) / (2 * size))
                pixels[x, y] = (r, g, b)
        path = os.path.join(save_dir, name)
        img.save(path)
        return path

    # 诈骗截图（2张）——红色调
    fraud_dir = os.path.join(DATA_DIR, 'image', 'raw', 'fraud')
    make_gradient((200, 50, 50), (100, 20, 20), 'fraud_001.png', fraud_dir)
    make_gradient((180, 40, 60), (120, 10, 30), 'fraud_002.png', fraud_dir)

    # 正常图片（2张）——绿色调
    normal_dir = os.path.join(DATA_DIR, 'image', 'raw', 'normal')
    make_gradient((50, 200, 50), (20, 100, 20), 'normal_001.png', normal_dir)
    make_gradient((60, 180, 80), (30, 120, 40), 'normal_002.png', normal_dir)

    # 篡改图片（2张）——蓝色调 + 人为修改部分像素模拟篡改
    tampered_dir = os.path.join(DATA_DIR, 'image', 'raw', 'tampered')
    p1 = make_gradient((50, 50, 200), (20, 20, 100), 'tampered_001.png', tampered_dir)
    p2 = make_gradient((60, 80, 180), (30, 40, 120), 'tampered_002.png', tampered_dir)

    # 对篡改图片做局部修改模拟PS痕迹
    for p in [p1, p2]:
        img = Image.open(p)
        pixels = img.load()
        for x in range(30, 70):
            for y in range(30, 70):
                pixels[x, y] = (255, 255, 0)  # 黄色块模拟篡改区域
        img.save(p)

    print(f"[图像] 生成 6 张图片 -> fraud/2, normal/2, tampered/2")


def main():
    print("=" * 60)
    print("生成合成样本数据")
    print("=" * 60)
    create_text_data()
    create_voice_data()
    create_image_data()
    print("\n合成数据生成完成，可运行预处理脚本验证流程。")


if __name__ == '__main__':
    main()
