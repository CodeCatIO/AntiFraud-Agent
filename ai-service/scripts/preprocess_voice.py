#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
语音数据预处理脚本

处理流程：加载 -> 重采样16kHz -> 单声道 -> 提取MFCC -> 数据增强（加噪/变速/变调）

输入：data/voice/raw/{fraud,normal}/ 下的 wav/mp3
输出：data/voice/processed/ 统一wav + mfcc_features.npy + labels.npy + stats.json

数据集来源：
  - AISHELL-1 中文语音：https://www.openslr.org/33/
  - Common Voice 中文：https://commonvoice.mozilla.org/zh-CN
  - 公开诈骗电话录音（需自录/模拟）
"""
import os
import json
import numpy as np
import librosa
import soundfile as sf

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AI_SERVICE_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(AI_SERVICE_DIR, 'data')
RAW_DIR = os.path.join(DATA_DIR, 'voice', 'raw')
PROCESSED_DIR = os.path.join(DATA_DIR, 'voice', 'processed')
STATS_DIR = os.path.join(DATA_DIR, 'voice', 'stats')

TARGET_SR = 16000
N_MFCC = 20

LABEL_MAP = {'fraud': 1, 'normal': 0}


def load_audio_files():
    """加载所有音频文件"""
    results = []
    for label_name, label in LABEL_MAP.items():
        sub_dir = os.path.join(RAW_DIR, label_name)
        if not os.path.isdir(sub_dir):
            print(f"  跳过（目录不存在）: {sub_dir}")
            continue
        files = [f for f in os.listdir(sub_dir) if f.endswith(('.wav', '.mp3', '.flac'))]
        for f in files:
            path = os.path.join(sub_dir, f)
            results.append((path, f, label_name, label))
        print(f"  {label_name}/: {len(files)} 个文件")
    return results


def process_audio(path):
    """处理单个音频文件：加载 -> 重采样 -> 单声道 -> MFCC"""
    # 加载（保留原始采样率）
    y, orig_sr = librosa.load(path, sr=None, mono=False)

    # 多声道转单声道
    if y.ndim > 1:
        y = np.mean(y, axis=0)

    # 重采样到目标采样率
    if orig_sr != TARGET_SR:
        y = librosa.resample(y, orig_sr=orig_sr, target_sr=TARGET_SR)

    duration = len(y) / TARGET_SR

    # 提取 MFCC
    mfcc = librosa.feature.mfcc(y=y, sr=TARGET_SR, n_mfcc=N_MFCC)
    mfcc_mean = np.mean(mfcc, axis=1)  # 时间维取均值 -> 20维向量

    return y, duration, mfcc_mean


def augment_audio(y, sr):
    """数据增强：加噪、变速、变调"""
    augmented = []

    # 1. 加噪
    noise = 0.005 * np.random.randn(len(y))
    y_noise = y + noise
    augmented.append(('noise', y_noise))

    # 2. 变速（0.9x 和 1.1x）
    y_fast = librosa.effects.time_stretch(y, rate=1.1)
    augmented.append(('speed_up', y_fast))

    y_slow = librosa.effects.time_stretch(y, rate=0.9)
    augmented.append(('speed_down', y_slow))

    # 3. 变调（+2 和 -2 半音）
    y_pitch_up = librosa.effects.pitch_shift(y, sr=sr, n_steps=2)
    augmented.append(('pitch_up', y_pitch_up))

    y_pitch_down = librosa.effects.pitch_shift(y, sr=sr, n_steps=-2)
    augmented.append(('pitch_down', y_pitch_down))

    return augmented


def main():
    print("=" * 60)
    print("语音数据预处理")
    print("=" * 60)

    # 1. 加载文件列表
    print("\n[1/4] 扫描音频文件...")
    audio_files = load_audio_files()
    if not audio_files:
        raise FileNotFoundError(
            f"未找到音频文件，请先在 {RAW_DIR}/{{fraud,normal}}/ 放入数据"
        )

    os.makedirs(PROCESSED_DIR, exist_ok=True)

    # 2. 处理每个文件
    print(f"\n[2/4] 处理音频（重采样16kHz + 单声道 + MFCC）...")
    all_mfcc = []
    all_labels = []
    total_duration = 0.0
    file_stats = {'fraud': 0, 'normal': 0}

    for path, filename, label_name, label in audio_files:
        y, duration, mfcc_mean = process_audio(path)
        all_mfcc.append(mfcc_mean)
        all_labels.append(label)
        total_duration += duration
        file_stats[label_name] += 1

        # 保存统一格式 wav
        out_name = f"{label_name}_{filename}"
        out_path = os.path.join(PROCESSED_DIR, out_name)
        sf.write(out_path, y, TARGET_SR)

    print(f"  处理 {len(audio_files)} 个文件，总时长 {total_duration:.2f}s")

    # 3. 数据增强
    print(f"\n[3/4] 数据增强（加噪/变速/变调）...")
    aug_count = 0
    for path, filename, label_name, label in audio_files:
        # 加载已处理的音频
        out_name = f"{label_name}_{filename}"
        processed_path = os.path.join(PROCESSED_DIR, out_name)
        y, _ = librosa.load(processed_path, sr=TARGET_SR)

        augmented = augment_audio(y, TARGET_SR)
        for aug_type, y_aug in augmented:
            aug_name = f"aug_{aug_type}_{label_name}_{filename}"
            aug_path = os.path.join(PROCESSED_DIR, aug_name)
            sf.write(aug_path, y_aug, TARGET_SR)

            # 增强样本的MFCC
            mfcc = librosa.feature.mfcc(y=y_aug, sr=TARGET_SR, n_mfcc=N_MFCC)
            all_mfcc.append(np.mean(mfcc, axis=1))
            all_labels.append(label)
            aug_count += 1

    print(f"  生成 {aug_count} 个增强样本")

    # 4. 保存特征和标签
    print(f"\n[4/4] 保存特征矩阵...")
    mfcc_array = np.array(all_mfcc)
    label_array = np.array(all_labels)
    np.save(os.path.join(PROCESSED_DIR, 'mfcc_features.npy'), mfcc_array)
    np.save(os.path.join(PROCESSED_DIR, 'labels.npy'), label_array)
    print(f"  MFCC: {mfcc_array.shape}, Labels: {label_array.shape}")

    # 统计
    os.makedirs(STATS_DIR, exist_ok=True)
    stats = {
        'total_samples': len(audio_files),
        'augmented_samples': aug_count,
        'total_with_augmentation': len(all_labels),
        'fraud_samples': file_stats['fraud'],
        'normal_samples': file_stats['normal'],
        'total_duration_sec': round(total_duration, 2),
        'total_duration_hours': round(total_duration / 3600, 4),
        'target_sample_rate': TARGET_SR,
        'mfcc_dimensions': N_MFCC,
        'augmentation_types': ['noise', 'speed_up', 'speed_down', 'pitch_up', 'pitch_down'],
    }
    with open(os.path.join(STATS_DIR, 'stats.json'), 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"  统计 -> {STATS_DIR}/stats.json")
    print(f"\n语音预处理完成。")


if __name__ == '__main__':
    main()
