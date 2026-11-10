#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
图像数据预处理脚本

处理流程：加载 -> resize 224x224 -> BGR->RGB -> 归一化(0-1) -> 数据增强（翻转/裁剪/加噪）

输入：data/image/raw/{fraud,normal,tampered}/ 下的 png/jpg
输出：data/image/processed/ 统一图片 + images.npy + labels.npy + stats.json

数据集来源：
  - CASIA v2 篡改图像：http://forensics.idealtest.org/
  - IMD20 篡改数据集：https://github.com/aim-group/imd
  - NIST16 图像篡改：https://www.nist.gov/
"""
import os
import json
import numpy as np
import cv2

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AI_SERVICE_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(AI_SERVICE_DIR, 'data')
RAW_DIR = os.path.join(DATA_DIR, 'image', 'raw')
PROCESSED_DIR = os.path.join(DATA_DIR, 'image', 'processed')
STATS_DIR = os.path.join(DATA_DIR, 'image', 'stats')

TARGET_SIZE = (224, 224)
LABEL_MAP = {'fraud': 1, 'normal': 0, 'tampered': 2}


def load_image_files():
    """加载所有图片文件"""
    results = []
    for label_name, label in LABEL_MAP.items():
        sub_dir = os.path.join(RAW_DIR, label_name)
        if not os.path.isdir(sub_dir):
            print(f"  跳过（目录不存在）: {sub_dir}")
            continue
        files = [
            f for f in os.listdir(sub_dir)
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp'))
        ]
        for f in files:
            path = os.path.join(sub_dir, f)
            results.append((path, f, label_name, label))
        print(f"  {label_name}/: {len(files)} 个文件")
    return results


def process_image(path):
    """处理单张图片：resize + RGB + 归一化"""
    img = cv2.imread(path)
    if img is None:
        raise ValueError(f"无法读取图片: {path}")

    # resize
    img = cv2.resize(img, TARGET_SIZE)

    # BGR -> RGB
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # 归一化到 0-1
    img = img.astype(np.float32) / 255.0

    return img


def augment_image(img):
    """数据增强：水平翻转、随机裁剪、高斯噪声"""
    augmented = []

    # 转回 uint8 处理
    img_uint8 = (img * 255).astype(np.uint8)

    # 1. 水平翻转
    flipped = cv2.flip(img_uint8, 1)
    augmented.append(('flip', flipped))

    # 2. 随机裁剪（偏移10像素后resize回224）
    h, w = img_uint8.shape[:2]
    dx, dy = np.random.randint(-10, 11, 2)
    x1 = max(0, dx)
    y1 = max(0, dy)
    x2 = min(w, w + dx)
    y2 = min(h, h + dy)
    cropped = img_uint8[y1:y2, x1:x2]
    if cropped.size > 0:
        cropped = cv2.resize(cropped, TARGET_SIZE)
    else:
        cropped = img_uint8.copy()
    augmented.append(('crop', cropped))

    # 3. 高斯噪声
    noise = np.random.normal(0, 10, img_uint8.shape).astype(np.int16)
    noisy = np.clip(img_uint8.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    augmented.append(('noise', noisy))

    return augmented


def main():
    print("=" * 60)
    print("图像数据预处理")
    print("=" * 60)

    # 1. 加载文件列表
    print("\n[1/4] 扫描图片文件...")
    image_files = load_image_files()
    if not image_files:
        raise FileNotFoundError(
            f"未找到图片文件，请先在 {RAW_DIR}/{{fraud,normal,tampered}}/ 放入数据"
        )

    os.makedirs(PROCESSED_DIR, exist_ok=True)

    # 2. 处理每张图片
    print(f"\n[2/4] 处理图片（resize 224x224 + RGB + 归一化）...")
    all_images = []
    all_labels = []
    file_stats = {'fraud': 0, 'normal': 0, 'tampered': 0}
    original_sizes = []

    for path, filename, label_name, label in image_files:
        # 记录原始尺寸
        img_raw = cv2.imread(path)
        if img_raw is not None:
            original_sizes.append(f"{img_raw.shape[1]}x{img_raw.shape[0]}")

        img = process_image(path)

        # 保存处理后的图片（uint8 PNG）
        out_name = f"{label_name}_{filename}"
        out_path = os.path.join(PROCESSED_DIR, out_name)
        cv2.imwrite(out_path, cv2.cvtColor((img * 255).astype(np.uint8), cv2.COLOR_RGB2BGR))

        all_images.append(img)
        all_labels.append(label)
        file_stats[label_name] += 1

    print(f"  处理 {len(image_files)} 张图片")

    # 3. 数据增强
    print(f"\n[3/4] 数据增强（翻转/裁剪/加噪）...")
    aug_count = 0
    for path, filename, label_name, label in image_files:
        img = process_image(path)
        augmented = augment_image(img)

        for aug_type, aug_img in augmented:
            aug_name = f"aug_{aug_type}_{label_name}_{filename}"
            aug_path = os.path.join(PROCESSED_DIR, aug_name)
            cv2.imwrite(aug_path, cv2.cvtColor(aug_img, cv2.COLOR_RGB2BGR))

            # 增强样本归一化
            aug_normalized = aug_img.astype(np.float32) / 255.0
            all_images.append(aug_normalized)
            all_labels.append(label)
            aug_count += 1

    print(f"  生成 {aug_count} 张增强图片")

    # 4. 保存特征和标签
    print(f"\n[4/4] 保存标签和统计...")
    image_array = np.array(all_images)
    label_array = np.array(all_labels)
    np.save(os.path.join(PROCESSED_DIR, 'images.npy'), image_array)
    np.save(os.path.join(PROCESSED_DIR, 'labels.npy'), label_array)
    print(f"  Images: {image_array.shape}, Labels: {label_array.shape}")

    # 统计
    os.makedirs(STATS_DIR, exist_ok=True)
    stats = {
        'total_samples': len(image_files),
        'augmented_samples': aug_count,
        'total_with_augmentation': len(all_labels),
        'fraud_samples': file_stats['fraud'],
        'normal_samples': file_stats['normal'],
        'tampered_samples': file_stats['tampered'],
        'target_size': f"{TARGET_SIZE[0]}x{TARGET_SIZE[1]}",
        'original_sizes': list(set(original_sizes)),
        'augmentation_types': ['flip', 'crop', 'noise'],
        'normalized': True,
    }
    with open(os.path.join(STATS_DIR, 'stats.json'), 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"  统计 -> {STATS_DIR}/stats.json")
    print(f"\n图像预处理完成。")


if __name__ == '__main__':
    main()
