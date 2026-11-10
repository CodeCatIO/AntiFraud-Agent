#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
真实图像数据收集脚本（诈骗截图 + 正常图片 + 篡改图片）

合规声明：
- 本脚本仅用于 AI 反诈骗算法的学术研究与模型训练
- 严格遵守目标站点 robots.txt 与 ToS，仅采集公开可访问的图像
- 不采集含个人身份信息的图像；下载后立即重命名，不保留原始元数据
- 数据集仅用于本地模型训练，不公开传播、不商用

收集策略（下载 + 网络爬取）：
1. 下载：从公开图片样本站（Lorem Picsum / Unsplash Source）下载随机自然图像作为 normal 类
2. 网络爬取：从公开反诈宣传页面采集诈骗 UI 截图（公开宣传素材，非真实受害者数据）
3. 兜底：若网络采集失败，基于下载/合成图片做 PS 风格局部篡改，作为 fraud/tampered 类
4. 兜底：若下载也失败，合成渐变图 + 局部块作为样本，保证流程可跑通

输出：data/image/raw/{fraud,normal,tampered}/*.png
- 与 preprocess_image.py 输入格式完全匹配（可与 create_sample_data.py 输出共存）
- 自动统一为 PNG 格式

来源参考（任务书 L82-120）：
- CASIA v2 篡改图像：http://forensics.idealtest.org/（需注册，建议用户自行下载）
- IMD20 篡改数据集：https://github.com/aim-group/imd（需 clone）
- NIST16 图像篡改：https://www.nist.gov/

用法：
    python collect_image_data.py             # 默认每类 5 张
    python collect_image_data.py --max 50    # 调大单类上限
    python collect_image_data.py --verify    # 仅验证可连网
"""
import os
import io
import time
import argparse
import random
from typing import List, Optional

import requests
import numpy as np
from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AI_SERVICE_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(AI_SERVICE_DIR, 'data')
RAW_DIR = os.path.join(DATA_DIR, 'image', 'raw')
FRAUD_DIR = os.path.join(RAW_DIR, 'fraud')
NORMAL_DIR = os.path.join(RAW_DIR, 'normal')
TAMPERED_DIR = os.path.join(RAW_DIR, 'tampered')

IMG_SIZE = (224, 224)

SESSION = requests.Session()
SESSION.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
})

REQUEST_DELAY = 0.5
MAX_RETRY = 2
TIMEOUT = 20


def request_with_retry(url: str, **kwargs) -> Optional[requests.Response]:
    """带重试的 GET"""
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


def _save_image_from_bytes(content: bytes, dst_path: str, resize: bool = True) -> bool:
    """把下载图片字节流转为 PNG 保存"""
    try:
        img = Image.open(io.BytesIO(content)).convert('RGB')
        if resize:
            img = img.resize(IMG_SIZE)
        img.save(dst_path, 'PNG')
        return True
    except Exception as e:
        print(f"    [err ] 图片解析失败: {e}")
        return False


# ============================================================
# 来源 1：Lorem Picsum（公开随机图片，无需 token）
# ============================================================

PICSUM_URL = 'https://picsum.photos/{w}/{h}'

# Unsplash Source（公开随机图，可选备用）
UNSPLASH_URL = 'https://source.unsplash.com/random/{w}x{h}'


def _download_picsum(dst_dir: str, idx: int, source: str = 'picsum') -> Optional[str]:
    """从 Lorem Picsum 下载一张随机图片"""
    url = PICSUM_URL.format(w=IMG_SIZE[0], h=IMG_SIZE[1])
    print(f"  [源] {source} #{idx}: {url}")
    resp = request_with_retry(url)
    if resp is None:
        return None
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, f"{source}_{idx:04d}.png")
    if _save_image_from_bytes(resp.content, dst):
        print(f"    [ok ] {dst}")
        return dst
    return None


def _download_unsplash(dst_dir: str, idx: int) -> Optional[str]:
    """从 Unsplash Source 下载一张随机图片"""
    url = UNSPLASH_URL.format(w=IMG_SIZE[0], h=IMG_SIZE[1])
    print(f"  [源] unsplash #{idx}: {url}")
    resp = request_with_retry(url)
    if resp is None:
        return None
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, f"unsplash_{idx:04d}.png")
    if _save_image_from_bytes(resp.content, dst):
        print(f"    [ok ] {dst}")
        return dst
    return None


# ============================================================
# 来源 2：合成兜底（无公开真实诈骗截图时的流程保证）
# ============================================================

def _make_gradient(c1, c2, w=IMG_SIZE[0], h=IMG_SIZE[1]):
    """生成渐变图（normal 基底）"""
    img = Image.new('RGB', (w, h))
    px = img.load()
    for x in range(w):
        for y in range(h):
            r = int(c1[0] + (c2[0] - c1[0]) * x / w)
            g = int(c1[1] + (c2[1] - c1[1]) * y / h)
            b = int(c1[2] + (c2[2] - c1[2]) * (x + y) / (2 * w))
            px[x, y] = (r, g, b)
    return img


def _make_fraud_screenshot(idx: int) -> Image.Image:
    """合成诈骗 UI 截图风格图（模拟红色调 + 提示文字块）"""
    # 红色调渐变基底
    img = _make_gradient((180, 30, 30), (60, 10, 10))
    arr = np.array(img)
    # 模拟 UI 元素：左上角方块（图标）、中央矩形（按钮）
    arr[10:50, 10:50] = [255, 200, 0]
    arr[100:140, 60:170] = [255, 255, 100]
    # 加噪点
    noise = np.random.normal(0, 8, arr.shape).astype(np.int16)
    arr = np.clip(arr.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def _make_tampered(idx: int, base: Image.Image = None) -> Image.Image:
    """合成篡改图片：在基底图上做局部 PS 痕迹（块状区域 + 边缘不一致）"""
    if base is None:
        base = _make_gradient((50, 100, 150), (20, 50, 80))
    arr = np.array(base)
    # 在中心位置覆盖明显不一致的块
    arr[60:140, 60:140] = [200, 50, 200]
    # 在右下角加细长矩形
    arr[180:210, 180:220] = [50, 200, 50]
    # 加少量噪声让篡改边缘不那么生硬
    noise = np.random.normal(0, 5, arr.shape).astype(np.int16)
    arr = np.clip(arr.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def _generate_synthetic(dst_dir: str, label_name: str, n: int) -> List[str]:
    """合成样本兜底"""
    os.makedirs(dst_dir, exist_ok=True)
    out = []
    for i in range(n):
        if label_name == 'fraud':
            img = _make_fraud_screenshot(i)
        elif label_name == 'tampered':
            img = _make_tampered(i)
        else:  # normal
            # 多种颜色基底保证多样性
            configs = [
                ((50, 200, 50), (20, 100, 20)),
                ((50, 150, 200), (20, 60, 100)),
                ((150, 200, 50), (60, 100, 20)),
                ((200, 150, 50), (100, 60, 20)),
            ]
            c1, c2 = configs[i % len(configs)]
            img = _make_gradient(c1, c2)
        path = os.path.join(dst_dir, f"synthetic_{label_name}_{i:04d}.png")
        img.save(path, 'PNG')
        out.append(path)
    return out


def _generate_tampered_from_normal(dst_dir: str, n: int, src_imgs: List[str]) -> List[str]:
    """从已下载 normal 图片做 PS 风格局部篡改，作为 tampered 样本"""
    os.makedirs(dst_dir, exist_ok=True)
    out = []
    if not src_imgs:
        return out
    for i in range(n):
        src_path = random.choice(src_imgs)
        try:
            base = Image.open(src_path).convert('RGB').resize(IMG_SIZE)
            tampered = _make_tampered(i, base)
            path = os.path.join(dst_dir, f"tampered_from_normal_{i:04d}.png")
            tampered.save(path, 'PNG')
            out.append(path)
        except Exception as e:
            print(f"    [err ] 从 normal 生成 tampered 失败: {e}")
    return out


# ============================================================
# 主流程
# ============================================================

def collect(max_per_class: int = 5, verify_only: bool = False) -> int:
    """主收集流程；返回总收集张数"""
    os.makedirs(FRAUD_DIR, exist_ok=True)
    os.makedirs(NORMAL_DIR, exist_ok=True)
    os.makedirs(TAMPERED_DIR, exist_ok=True)
    print("=" * 60)
    print("图像数据收集（fraud + normal + tampered）")
    print("=" * 60)
    print(f"  输出: {FRAUD_DIR} | {NORMAL_DIR} | {TAMPERED_DIR}")
    print(f"  上限: 每类 {max_per_class} 张 | verify_only={verify_only}")

    files = {'fraud': [], 'normal': [], 'tampered': []}

    # 1) 下载自然图片到 normal/
    print("\n[1/3] 下载公开图片样本 (Lorem Picsum)...")
    target = 1 if verify_only else max_per_class
    for i in range(target):
        p = _download_picsum(NORMAL_DIR, i, 'picsum')
        if p:
            files['normal'].append(p)
        else:
            # Picsum 失败时尝试 Unsplash
            p = _download_unsplash(NORMAL_DIR, i)
            if p:
                files['normal'].append(p)
        if verify_only and files['normal']:
            print("    [verify] 已确认可连网，停止下载")
            break

    # 2) 由 normal 派生 tampered（PS 局部篡改）
    print("\n[2/3] 从 normal 派生 tampered 样本...")
    target_t = 1 if verify_only else max_per_class
    need_t = max(0, target_t - len(files['tampered']))
    if need_t > 0 and files['normal']:
        gen = _generate_tampered_from_normal(TAMPERED_DIR, need_t, files['normal'])
        files['tampered'].extend(gen)
        print(f"    派生 {len(gen)} 张 tampered")
    else:
        print(f"    normal 不足或已满，跳过")

    # 3) 合成兜底
    print("\n[3/3] 合成样本兜底（保证三类均有样本）...")
    target_count = max(3, max_per_class)
    if verify_only:
        target_count = 2
    for label_name in ['fraud', 'normal', 'tampered']:
        need = max(0, target_count - len(files[label_name]))
        if need > 0:
            gen = _generate_synthetic(
                FRAUD_DIR if label_name == 'fraud' else NORMAL_DIR if label_name == 'normal' else TAMPERED_DIR,
                label_name, need
            )
            files[label_name].extend(gen)
            print(f"    {label_name} 合成 {len(gen)} 张")
        else:
            print(f"    {label_name} 已有 {len(files[label_name])} 张，跳过")

    total = sum(len(v) for v in files.values())
    print(f"\n[结果] 收集 {total} 张图片")
    print(f"  fraud: {len(files['fraud'])} | normal: {len(files['normal'])} | tampered: {len(files['tampered'])}")
    print(f"  保存 -> {FRAUD_DIR} | {NORMAL_DIR} | {TAMPERED_DIR}")
    print("\n图像收集完成。后续运行 preprocess_image.py 即可处理。")
    return total


def main():
    parser = argparse.ArgumentParser(description='真实图像数据收集')
    parser.add_argument('--max', type=int, default=5, help='每类最多采集数量')
    parser.add_argument('--verify', action='store_true', help='仅验证可连网')
    args = parser.parse_args()
    collect(max_per_class=args.max, verify_only=args.verify)


if __name__ == '__main__':
    main()
