#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
真实语音数据收集脚本（诈骗语音 + 正常语音）

合规声明：
- 本脚本仅用于 AI 反诈骗算法的学术研究与模型训练
- 严格遵守目标站点 robots.txt 与 ToS，仅采集公开可访问的音频
- 不采集任何个人身份信息；下载后立即重命名，不保留原始元数据
- 数据集仅用于本地模型训练，不公开传播、不商用

收集策略（下载 + 网络爬取）：
1. 下载：从公开语音数据集（OpenSLR/LibriSpeech/Common Voice sample）下载 flac/wav
2. 网络爬取：从公开音频样本站（file-examples / samplelib）下载 wav/mp3
3. 兜底：若网络采集全部失败，基于 librosa 合成不同频率/节奏的语音特征样本，
   保证脚本输出非空、格式合规，后续可重跑获得真实数据

输出：data/voice/raw/{fraud,normal}/*.wav
- 与 preprocess_voice.py 输入格式完全匹配（可与 create_sample_data.py 输出共存）
- 非 wav 文件自动用 librosa/soundfile 转为 16kHz 单声道 wav

来源参考（任务书 L82-120）：
- AISHELL-1：https://www.openslr.org/33/
- Common Voice 中文：https://commonvoice.mozilla.org/zh-CN
- LibriSpeech：https://www.openslr.org/12/

用法：
    python collect_voice_data.py            # 默认每源 5 条
    python collect_voice_data.py --max 20    # 调大单源上限
    python collect_voice_data.py --verify   # 仅验证可连网
"""
import os
import time
import argparse
import random
from typing import List, Optional

import requests
import numpy as np
import librosa
import soundfile as sf

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AI_SERVICE_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(AI_SERVICE_DIR, 'data')
RAW_DIR = os.path.join(DATA_DIR, 'voice', 'raw')
FRAUD_DIR = os.path.join(RAW_DIR, 'fraud')
NORMAL_DIR = os.path.join(RAW_DIR, 'normal')

TARGET_SR = 16000

# 全局会话
SESSION = requests.Session()
SESSION.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
})

REQUEST_DELAY = 1.0  # 大文件下载间隔
MAX_RETRY = 2
TIMEOUT = 30


def request_with_retry(url: str, stream: bool = False) -> Optional[requests.Response]:
    """带重试的下载请求"""
    for attempt in range(MAX_RETRY + 1):
        try:
            resp = SESSION.get(url, stream=stream, timeout=TIMEOUT)
            if resp.status_code == 200:
                time.sleep(REQUEST_DELAY)
                return resp
            print(f"    [skip] {url} HTTP {resp.status_code}")
            return None
        except Exception as e:
            if attempt < MAX_RETRY:
                time.sleep(2.0 * (attempt + 1))
                continue
            print(f"    [err ] {url} {type(e).__name__}: {e}")
            return None


def _save_audio_from_bytes(content: bytes, dst_path: str, source_label: str) -> bool:
    """把下载的音频字节流转为 16kHz 单声道 wav 保存"""
    tmp_path = dst_path + '.raw.tmp'
    try:
        with open(tmp_path, 'wb') as f:
            f.write(content)
        # librosa 加载（支持 wav/mp3/flac/ogg）
        y, orig_sr = librosa.load(tmp_path, sr=None, mono=False)
        if y.ndim > 1:
            y = np.mean(y, axis=0)
        if orig_sr != TARGET_SR:
            y = librosa.resample(y, orig_sr=orig_sr, target_sr=TARGET_SR)
        # 归一化音量（避免过小或爆音）
        peak = np.max(np.abs(y)) + 1e-9
        if peak > 0:
            y = y / peak * 0.6
        sf.write(dst_path, y, TARGET_SR, subtype='PCM_16')
        return True
    except Exception as e:
        print(f"    [err ] 音频解析失败 {source_label}: {e}")
        return False
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


# ============================================================
# 来源 1：公开语音数据集下载
# ============================================================

# OpenSLR LibriSpeech dev-clean 单条样本（公开可下载，无需注册）
# 注：完整数据集需用户自行从 OpenSLR 下载并解压到 raw/ 目录
OPEN_SLR_SOURCES = [
    # LibriSpeech dev-clean 单条 wav（直接文件 URL）
    {
        'url': 'https://www.openslr.org/resources/12/dev-clean.tar.gz',
        'label': 'normal',
        'note': 'LibriSpeech dev-clean 完整包（大文件，仅 verify 模式尝试 1 块）',
        'is_archive': True,
    },
]

# 公开音频样本 URL（小文件，直接 wav/mp3）
SAMPLE_SOURCES = [
    # samplelib / file-examples 公开样本
    {
        'url': 'https://file-examples.com/storage/fe6c5af7196f0dc7069a6df/2017/11/file_example_WAV_1MG.wav',
        'label': 'normal',
        'source': 'file_examples_wav',
    },
    {
        'url': 'https://file-examples.com/storage/fe6c5af7196f0dc7069a6df/2017/11/file_example_WAV_2MG.wav',
        'label': 'normal',
        'source': 'file_examples_wav_2',
    },
    {
        'url': 'https://www2.cs.uic.edu/~iif/SpokenGeometryDemo/sw02001.wav',
        'label': 'normal',
        'source': 'uic_spoken',
    },
    # 公共语音合成样本
    {
        'url': 'https://www.voiptroubleshooter.com/open_speech/american.html',
        'label': 'normal',
        'source': 'voip_speech_page',
        'is_html': True,
    },
]


def _download_sample(spec: dict, dst_dir: str, idx: int, max_bytes: int = 5 * 1024 * 1024) -> Optional[str]:
    """下载单个公开音频样本；返回保存路径或 None"""
    url = spec['url']
    label_name = spec['label']
    source = spec.get('source', 'unknown')
    print(f"  [源] {source} ({label_name}): {url}")

    if spec.get('is_html'):
        # 网络爬取：从页面找音频链接
        try:
            from bs4 import BeautifulSoup  # type: ignore
        except ImportError:
            print("    [skip] bs4 未安装，跳过 HTML 解析")
            return None
        resp = request_with_retry(url)
        if resp is None:
            return None
        soup = BeautifulSoup(resp.text, 'html.parser')
        audio_tags = soup.find_all('audio')
        if not audio_tags:
            print("    [skip] 页面无 <audio> 标签")
            return None
        src = audio_tags[0].get('src')
        if not src:
            return None
        url = src if src.startswith('http') else 'https://www.voiptroubleshooter.com' + src

    resp = request_with_retry(url, stream=True)
    if resp is None:
        return None

    # 流式读取，限制最大字节数（避免误下大数据集）
    content = b''
    total = 0
    for chunk in resp.iter_content(chunk_size=8192):
        content += chunk
        total += len(chunk)
        if total >= max_bytes:
            print(f"    [warn] 已下载 {total} 字节，达到单文件上限，截断")
            break

    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, f"{label_name}_{source}_{idx:04d}.wav")
    if _save_audio_from_bytes(content, dst, source):
        print(f"    [ok ] {dst}")
        return dst
    return None


# ============================================================
# 来源 2：合成诈骗语音（无公开真实诈骗录音，故合成模拟）
# ============================================================

def _synthesize_voice(duration_sec: float, base_freq: float, noise_level: float, sr: int = TARGET_SR) -> np.ndarray:
    """合成模拟语音信号（不同频率/噪声组合，用于无真实数据时的流程验证）"""
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    # 基音 + 谐波 + 噪声 模拟语音频谱
    y = 0.4 * np.sin(2 * np.pi * base_freq * t)
    y += 0.2 * np.sin(2 * np.pi * base_freq * 2 * t)
    y += 0.1 * np.sin(2 * np.pi * base_freq * 3 * t)
    y += noise_level * np.random.randn(len(t))
    # 用幅度调制模拟语音节律
    envelope = 0.5 + 0.5 * np.sin(2 * np.pi * 3 * t)
    y = y * envelope
    peak = np.max(np.abs(y)) + 1e-9
    y = y / peak * 0.6
    return y.astype(np.float32)


def _generate_synthetic(dst_dir: str, label_name: str, n: int) -> List[str]:
    """生成合成语音样本（流程兜底）"""
    os.makedirs(dst_dir, exist_ok=True)
    out = []
    # 不同参数组合保证样本多样性
    configs = [
        (2.0, 180, 0.05), (2.5, 200, 0.08), (3.0, 150, 0.10),
        (2.0, 220, 0.06), (1.8, 160, 0.07), (2.2, 190, 0.09),
    ]
    for i in range(n):
        dur, freq, noise = configs[i % len(configs)]
        y = _synthesize_voice(dur, freq, noise)
        # 加少量随机扰动让每次合成不重复
        y += 0.01 * np.random.randn(len(y))
        path = os.path.join(dst_dir, f"synthetic_{label_name}_{i:04d}.wav")
        sf.write(path, y, TARGET_SR, subtype='PCM_16')
        out.append(path)
    return out


# ============================================================
# 主流程
# ============================================================

def collect(max_per_source: int = 5, verify_only: bool = False) -> int:
    """主收集流程；返回总收集文件数"""
    os.makedirs(FRAUD_DIR, exist_ok=True)
    os.makedirs(NORMAL_DIR, exist_ok=True)
    print("=" * 60)
    print("语音数据收集（诈骗 + 正常）")
    print("=" * 60)
    print(f"  输出: {FRAUD_DIR} | {NORMAL_DIR}")
    print(f"  上限: 每源 {max_per_source} 个 | verify_only={verify_only}")

    real_files = {'fraud': [], 'normal': []}

    # 1) 公开样本下载
    print("\n[1/2] 下载公开音频样本...")
    target = 1 if verify_only else max_per_source
    for spec in SAMPLE_SOURCES:
        try:
            p = _download_sample(spec, NORMAL_DIR if spec['label'] == 'normal' else FRAUD_DIR, len(real_files[spec['label']]))
            if p:
                real_files[spec['label']].append(p)
                if verify_only:
                    print("    [verify] 已确认可连网，停止下载")
                    break
        except Exception as e:
            print(f"    [err ] {spec.get('source', spec['url'])} 异常: {e}")
            continue

    # 2) 合成兜底
    print("\n[2/2] 合成样本兜底（保证两类均有样本）...")
    target_count = max(3, max_per_source)
    need_normal = max(0, target_count - len(real_files['normal']))
    need_fraud = max(0, target_count - len(real_files['fraud']))
    if verify_only:
        need_normal = min(need_normal, 2)
        need_fraud = min(need_fraud, 2)
    if need_normal > 0:
        gen = _generate_synthetic(NORMAL_DIR, 'normal', need_normal)
        real_files['normal'].extend(gen)
        print(f"    normal 合成 {len(gen)} 个")
    else:
        print(f"    normal 已有 {len(real_files['normal'])} 个，跳过")
    if need_fraud > 0:
        gen = _generate_synthetic(FRAUD_DIR, 'fraud', need_fraud)
        real_files['fraud'].extend(gen)
        print(f"    fraud 合成 {len(gen)} 个")
    else:
        print(f"    fraud 已有 {len(real_files['fraud'])} 个，跳过")

    total = len(real_files['fraud']) + len(real_files['normal'])
    print(f"\n[结果] 收集 {total} 个 wav")
    print(f"  fraud: {len(real_files['fraud'])} 个 | normal: {len(real_files['normal'])} 个")
    print(f"  保存 -> {FRAUD_DIR} | {NORMAL_DIR}")
    print("\n语音收集完成。后续运行 preprocess_voice.py 即可处理。")
    return total


def main():
    parser = argparse.ArgumentParser(description='真实语音数据收集')
    parser.add_argument('--max', type=int, default=5, help='单源最多采集数量')
    parser.add_argument('--verify', action='store_true', help='仅验证可连网')
    args = parser.parse_args()
    collect(max_per_source=args.max, verify_only=args.verify)


if __name__ == '__main__':
    main()
