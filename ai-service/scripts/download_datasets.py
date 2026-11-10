#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
反诈语音/图片公开数据集下载与自动归位脚本
================================================

只收录“免登录、直链可达、来源可追溯”的公开数据集（链接均经过实测）。
下载后自动解压，并把媒体文件扁平归位到预处理脚本约定的目录：

    data/voice/raw/{fraud,normal}/        支持 .wav/.mp3/.flac
    data/image/raw/{fraud,normal,tampered}/  支持 .png/.jpg/.jpeg/.bmp

注意：当前语音/图片模型的 fraud 类语义是“AI 合成/篡改”，不是“诈骗话术内容”。
    - 语音 fraud   = TTS/声码器伪造的人声（WaveFake、CFAD 等）
    - 图片 fraud   = AI 生成图（COCOAI）
    - 图片 tampered = PS 拼接/复制移动篡改图（CASIA、IMD2020）

合规：各数据集许可证不同（多为 CC/学术用途），仅限学术研究与本地训练，
    请勿二次分发；ASVspoof/CFAD 等请遵守其 license 条款。

用法：
    python scripts/download_datasets.py --list                 # 查看可用数据源
    python scripts/download_datasets.py --verify               # 只探测链接/大小，不下载
    python scripts/download_datasets.py --start-voice         # 语音起步包（hf-mirror，933真人+933合成）
    python scripts/download_datasets.py --start-image         # 图片起步包（hf-mirror，539 AI图+435真实图）
    python scripts/download_datasets.py --only hf-fakeaudio,hf-aiart --max-files 20   # 小规模试跑
    python scripts/download_datasets.py --only imd2020        # PS篡改图(原图+篡改，国外源慢,593MB)
    python scripts/download_datasets.py --only cocoai-ai --cocoai-parts 1   # 更多AI生成图（需 pyarrow）
    python scripts/download_datasets.py --include-huge --only aishell1      # 大型源需显式放行

断点续传：归档下载到 data/downloads/，中断后重跑自动续传；已完成的解压/归位会跳过。
"""
import os
import sys
import json
import time
import shutil
import fnmatch
import zipfile
import tarfile
import argparse
from datetime import datetime, timezone

import requests

# ---------------------------------------------------------------------------
# 路径
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AI_SERVICE_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(AI_SERVICE_DIR, 'data')
DL_DIR = os.path.join(DATA_DIR, 'downloads')           # 归档缓存
EXTRACT_ROOT = os.path.join(DL_DIR, 'extracted')      # 解压目录
AUDIT_LOG = os.path.join(DL_DIR, 'place_manifest.jsonl')

VOICE_RAW = os.path.join(DATA_DIR, 'voice', 'raw')
IMAGE_RAW = os.path.join(DATA_DIR, 'image', 'raw')

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
      'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36')
SESSION = requests.Session()
SESSION.headers.update({'User-Agent': UA})

TIMEOUT = 60
MAX_RETRY = 3
CHUNK = 1 << 20  # 1 MiB

VOICE_EXTS = ('.wav', '.mp3', '.flac', '.ogg', '.m4a')
IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.bmp')
# 需转码才能被 preprocess_image.py 接受的图片格式（统一用 Pillow 转 png）
IMAGE_CONVERT_EXTS = ('.tif', '.tiff', '.webp', '.gif')


# ---------------------------------------------------------------------------
# 数据源清单（每条 URL 均已用 HEAD/GET 实测；size 为实测字节数，0 表示分流动态）
# rules: 在“解压后相对路径（正斜杠）”上按顺序匹配，决定归位标签；
#        支持 *（不跨目录）、**（跨任意目录）、?
# ---------------------------------------------------------------------------
# 速度说明（本机实测，仅参考）：hf-mirror 国内镜像 ~0.65MB/s（最快）；
# OpenSLR/COCO/IMD2020 等国外学术源 ~0.02-0.05MB/s，大包请耐心等待或自行用下载工具。
SOURCES = [
    # ========== 快速起步：hf-mirror 散文件（无需 pyarrow，国内可直连）==========
    {
        'id': 'hf-fakeaudio', 'modality': 'voice', 'huge': False, 'special': 'hf_tree',
        'name': 'Deepfake Audio Detection v4（933真人 vs 933条ElevenLabs合成，起步推荐）',
        'size_mb': 200, 'license': 'CC BY 4.0',
        'hf_repo': 'garystafford/deepfake-audio-detection',
        'rules': [('real/**', 'normal'), ('fake/**', 'fraud')],
        'note': 'yt_*=真人YouTube语音(normal)，el_*=ElevenLabs TTS合成(fraud)，flac切片',
    },
    {
        'id': 'hf-aiart', 'modality': 'image', 'huge': False, 'special': 'hf_tree',
        'name': 'AI-Generated vs Real Images（539张AI艺术图 vs 435张真实图，起步推荐）',
        'size_mb': 300, 'license': 'CC BY 4.0',
        'hf_repo': 'Hemg/AI-Generated-vs-Real-Images-Datasets',
        'rules': [('AiArtData/**', 'fraud'), ('RealArt/**', 'normal')],
        'note': 'AI 生成图(fraud) 与真实艺术品照片(normal)；webp/gif 自动转 png',
    },
    # ========== 图片：篡改检测（PS 拼接/复制移动）==========
    # 说明：CASIA v1/v2 完整原图(Au/Tp) 官方在 forensics.idealtest.org 需注册申请，
    # GitHub 上的 casia*groundtruth 仓库只含 _gt 二值掩码（不能当分类样本），故不收录。
    {
        'id': 'imd2020', 'modality': 'image', 'huge': False,
        'name': 'IMD2020 真实场景复杂编辑篡改数据集（原图+篡改图，国外源较慢）',
        'size_mb': 593, 'license': 'research use',
        'files': [{
            'url': 'https://staff.utia.cas.cz/novozada/db/IMD2020.zip',
            'fname': 'IMD2020.zip',
        }],
        # 实测结构：<case>/<case>_orig.jpg 原图；<id>_0.jpg/png 篡改图；<id>_0_mask.png 掩码(排除)
        'rules': [('**/*_mask*', 'SKIP'), ('**/*_orig*', 'normal'),
                  ('**/*.jpg', 'tampered'), ('**/*.jpeg', 'tampered'),
                  ('**/*.png', 'tampered')],
        'note': '414 组案例：*_orig* 为原图(normal)，其余图片为篡改图(tampered)，mask 已排除',
    },
    {
        'id': 'coco-val2017', 'modality': 'image', 'huge': False,
        'name': 'MS COCO val2017 真实照片（正常类负样本，国外源慢）',
        'size_mb': 816, 'license': 'COCO License (CC BY 4.0)',
        'files': [{
            'url': 'http://images.cocodataset.org/zips/val2017.zip',
            'fname': 'val2017.zip',
        }],
        'rules': [('**/*.jpg', 'normal'), ('**/*.jpeg', 'normal'), ('**/*.png', 'normal')],
        'note': '5000 张真实自然图像',
    },
    {
        'id': 'cocoai-ai', 'modality': 'image', 'huge': False, 'special': 'cocoai_parquet',
        'name': 'MS COCOAI / Defactify4 AI生成图（SD3/SDXL/DALL-E3/MJv6）',
        'size_mb': 340, 'license': 'CC BY 4.0', 'requires': ['pyarrow'],
        'parts': ['validation-00000-of-00002.parquet'],
        'url_tpl': 'https://hf-mirror.com/datasets/Rajarshi-Roy-research/Defactify_Image_Dataset/resolve/main/data/{part}',
        'rules': [],
        'note': '经 hf-mirror 下载；Label_A: 0=real->normal, 1=AI->fraud；每分片约340MB/4500张',
    },
    # ================= 语音：真人正常类（国外源慢）=================
    {
        'id': 'librispeech-dev-clean', 'modality': 'voice', 'huge': False,
        'name': 'LibriSpeech dev-clean 真人朗读（英文，正常类负样本）',
        'size_mb': 338, 'license': 'CC BY 4.0',
        'files': [{
            'url': 'https://www.openslr.org/resources/12/dev-clean.tar.gz',
            'fname': 'dev-clean.tar.gz',
        }],
        'rules': [('**/*.flac', 'normal'), ('**/*.wav', 'normal')],
        'note': '约2700条清晰真人语音(flac)，preprocess_voice 原生支持',
    },
    # ================= 大型源（默认跳过，--include-huge 放行）=================
    {
        'id': 'aishell1', 'modality': 'voice', 'huge': True, 'nested_tgz': True,
        'name': 'AISHELL-1 中文普通话语料（178人，正常类）',
        'size_mb': 15583, 'license': 'Apache 2.0 (academic)',
        'files': [{
            'url': 'https://www.openslr.org/resources/33/data_aishell.tgz',
            'fname': 'data_aishell.tgz',
        }],
        'rules': [('**/*.wav', 'normal')],
        'note': '约14万条中文真人语音；tgz 内含 wav 分卷 tgz，脚本自动二次解压',
    },
    {
        'id': 'wavefake', 'modality': 'voice', 'huge': True,
        'name': 'WaveFake AI合成语音（10种TTS/声码器，伪造类正样本）',
        'size_mb': 28919, 'license': 'CC BY 4.0',
        'files': [{
            'url': 'https://zenodo.org/api/records/5642694/files/generated_audio.zip/content',
            'fname': 'generated_audio.zip',
        }],
        'rules': [('**/*.wav', 'fraud'), ('**/*.flac', 'fraud'), ('**/*.mp3', 'fraud')],
        'note': '10.4万条生成语音全部归 fraud；真人底库请另配 LibriSpeech/LJSpeech',
    },
]

START_IMAGE = ['hf-aiart']
START_VOICE = ['hf-fakeaudio']


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------
def log(msg):
    print(msg, flush=True)


def by_id(src_id):
    for s in SOURCES:
        if s['id'] == src_id:
            return s
    raise KeyError(f'未知数据源: {src_id}（用 --list 查看）')


def raw_root(modality):
    return VOICE_RAW if modality == 'voice' else IMAGE_RAW


def label_dir(modality, label):
    p = os.path.join(raw_root(modality), label)
    os.makedirs(p, exist_ok=True)
    return p


def _pat_to_regex(pattern):
    """支持 ** 跨目录、* 不跨目录、? 单字符"""
    out = '(?is)^'
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if c == '*':
            if i + 1 < len(pattern) and pattern[i + 1] == '*':
                out += '.*'
                i += 2
                if i < len(pattern) and pattern[i] == '/':
                    i += 1
                continue
            out += '[^/]*'
        elif c == '?':
            out += '.'
        elif c == '.':
            out += r'\.'
        else:
            out += re_escape(c)
        i += 1
    return out + '$'


def re_escape(c):
    import re
    return re.escape(c)


def match_rules(rel_posix, rules):
    import re
    for pat, label in rules:
        if re.match(_pat_to_regex(pat), rel_posix):
            return label
    return None


def probe_url(url):
    """返回 (ok, status, size_bytes, final_url)"""
    try:
        r = SESSION.get(url, stream=True, timeout=TIMEOUT, allow_redirects=True, verify=False)
        cl = r.headers.get('Content-Length')
        size = int(cl) if cl and cl.isdigit() else 0
        r.close()
        return r.status_code == 200, r.status_code, size, r.url
    except requests.exceptions.RequestException as e:
        return False, type(e).__name__, 0, str(e)[:80]


def download_resume(url, dst):
    """带 Range 断点续传、重试退避的下载。"""
    tmp = dst + '.part'
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    have = os.path.getsize(tmp) if os.path.exists(tmp) else 0

    headers = {}
    if have:
        headers['Range'] = f'bytes={have}-'
    for attempt in range(MAX_RETRY + 1):
        try:
            with SESSION.get(url, headers=headers, stream=True, timeout=TIMEOUT,
                             allow_redirects=True, verify=False) as r:
                if have and r.status_code == 200:
                    # 服务器不支持续传/资源已变，从头来
                    have = 0
                    mode = 'wb'
                elif r.status_code in (200, 206):
                    mode = 'ab' if have else 'wb'
                else:
                    raise requests.RequestException(f'HTTP {r.status_code}')
                total = r.headers.get('Content-Length')
                total = int(total) if total and total.isdigit() else 0
                total += have if mode == 'ab' else 0
                last_print = [time.time()]
                with open(tmp, mode) as f:
                    for chunk in r.iter_content(CHUNK):
                        if chunk:
                            f.write(chunk)
                            have += len(chunk)
                            now = time.time()
                            if now - last_print[0] > 2:
                                if total:
                                    log(f'\r    {have/1e6:8.1f}/{total/1e6:.1f} MB '
                                        f'({have*100//total}%)', )
                                else:
                                    log(f'\r    {have/1e6:8.1f} MB')
                                last_print[0] = now
                # 完整性判断（有 Content-Length 时严格校验）
                if total and have < total:
                    raise requests.RequestException(f'下载不完整 {have}/{total}')
                os.replace(tmp, dst)
                log(f'\r    完成: {os.path.basename(dst)} ({have/1e6:.1f} MB)          ')
                return have
        except requests.exceptions.RequestException as e:
            if attempt < MAX_RETRY:
                wait = 2 ** attempt
                log(f'    下载中断({type(e).__name__}: {str(e)[:60]})，{wait}s 后续传…')
                time.sleep(wait)
                have = os.path.getsize(tmp) if os.path.exists(tmp) else 0
                headers = {'Range': f'bytes={have}-'} if have else {}
                continue
            raise


def _is_within(base, target):
    base = os.path.abspath(base)
    target = os.path.abspath(target)
    return os.path.commonpath([base, target]) == base


def extract_archive(archive, out_dir):
    """安全解压 zip/tar，防路径穿越。"""
    os.makedirs(out_dir, exist_ok=True)
    low = archive.lower()
    if low.endswith('.zip'):
        with zipfile.ZipFile(archive) as z:
            for n in z.namelist():
                if not _is_within(out_dir, os.path.join(out_dir, n)):
                    raise RuntimeError(f'压缩包含非法路径: {n}')
            z.extractall(out_dir)
    elif low.endswith(('.tar.gz', '.tgz', '.tar', '.tar.bz2')):
        with tarfile.open(archive) as t:
            for m in t.getmembers():
                if not _is_within(out_dir, os.path.join(out_dir, m.name)):
                    raise RuntimeError(f'压缩包含非法路径: {m.name}')
            t.extractall(out_dir)
    else:
        raise ValueError(f'不支持的压缩格式: {archive}')


def expand_nested_tgz(out_dir):
    """AISHELL：data_aishell.tgz 解出的 wav/*.tgz 再解一层。"""
    for root, _, files in os.walk(out_dir):
        for f in files:
            if f.endswith('.tgz'):
                inner = os.path.join(root, f)
                log(f'    二次解压: {f}')
                try:
                    with tarfile.open(inner) as t:
                        t.extractall(root)
                    os.remove(inner)
                except (tarfile.TarError, OSError) as e:
                    log(f'    [warn] 内层 tgz 解压失败 {f}: {e}')


def convert_image_if_needed(src_bytes_or_path, dst_dir, new_stem, is_bytes=False):
    """tif/tiff/webp/gif 用 Pillow 转 png（preprocess_image 不识别这些格式）。"""
    try:
        from PIL import Image
        import io as _io
        dst = os.path.join(dst_dir, new_stem + '.png')
        fp = _io.BytesIO(src_bytes_or_path) if is_bytes else src_bytes_or_path
        with Image.open(fp) as im:
            im.convert('RGB').save(dst, 'PNG')
        return dst
    except Exception as e:
        log(f'    [warn] 图片转码失败: {e}')
        return None


def place_files(src, extracted_dir, max_files=None, move=False):
    """按 rules 把媒体文件扁平归位到 raw/<label>/。返回 {label: count}。"""
    modality = src['modality']
    allowed = VOICE_EXTS if modality == 'voice' else IMAGE_EXTS
    counts = {}
    placed = 0
    for root, _, files in os.walk(extracted_dir):
        for f in files:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, extracted_dir).replace('\\', '/')
            low = f.lower()
            label = match_rules(rel, src['rules'])
            if not label or label == 'SKIP':
                continue
            ext = os.path.splitext(low)[1]
            dst_dir = label_dir(modality, label)
            stem = f"{src['id']}__{placed:07d}"
            dst = None
            if ext in allowed:
                dst = os.path.join(dst_dir, stem + ext)
            elif modality == 'image' and ext in IMAGE_CONVERT_EXTS:
                dst = convert_image_if_needed(full, dst_dir, stem)
            if not dst:
                continue
            if not os.path.exists(dst):
                shutil.move(full, dst) if move else shutil.copy2(full, dst)
            counts[label] = counts.get(label, 0) + 1
            placed += 1
            if max_files and counts[label] >= max_files:
                # 该标签达到上限：把它从规则里摘掉
                src['rules'] = [(p, l) for (p, l) in src['rules'] if l != label]
                if not src['rules']:
                    return counts
    return counts


def audit(source_id, label, count, extra=None):
    os.makedirs(os.path.dirname(AUDIT_LOG), exist_ok=True)
    rec = {'retrieved_at': datetime.now(timezone.utc).isoformat(),
           'source_id': source_id, 'label': label, 'count': count}
    if extra:
        rec.update(extra)
    with open(AUDIT_LOG, 'a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')


# ---------------------------------------------------------------------------
# COCOAI parquet 特殊处理
# ---------------------------------------------------------------------------
def handle_cocoai(src, args):
    try:
        import pyarrow.parquet as pq
    except ImportError:
        log('  [skip] 该源需要 pyarrow 解析 parquet：pip install pyarrow（不会自动安装）')
        return
    n_parts = max(1, args.cocoai_parts)
    total_counts = {}
    for part in src['parts'][:n_parts]:
        url = src['url_tpl'].format(part=part)
        archive = os.path.join(DL_DIR, f"cocoai_{part}")
        if not os.path.exists(archive):
            download_resume(url, archive)
        else:
            log(f'  已存在，跳过下载: {os.path.basename(archive)}')
        log(f'  解析 parquet: {part}')
        table = pq.read_table(archive, columns=['Image', 'Label_A'])
        imgs = table.column('Image').to_pylist()
        labels = table.column('Label_A').to_pylist()
        n_dir = label_dir('image', 'normal')
        f_dir = label_dir('image', 'fraud')
        kept = 0
        for i, (im, lab) in enumerate(zip(imgs, labels)):
            if args.max_files and kept >= args.max_files:
                break
            raw = (im or {}).get('bytes')
            if not raw:
                continue
            label = 'fraud' if int(lab) == 1 else 'normal'
            orig = (im.get('path') or 'img.png').lower()
            ext = '.jpg' if orig.endswith(('.jpg', '.jpeg')) else '.png'
            dst = os.path.join(f_dir if label == 'fraud' else n_dir,
                               f"cocoai__{part[:-8].replace('-', '_')}_{i:06d}{ext}")
            if not os.path.exists(dst):
                with open(dst, 'wb') as f:
                    f.write(raw)
            total_counts[label] = total_counts.get(label, 0) + 1
            kept += 1
        log(f'    {part}: 本批累计 {total_counts}')
    for label, c in total_counts.items():
        audit(src['id'], label, c, {'license': src['license'], 'url': src['url_tpl']})


# ---------------------------------------------------------------------------
# HuggingFace 散文件仓库（hf-mirror，国内可直连，无需 pyarrow）
# ---------------------------------------------------------------------------
def fetch_bytes(url, tries=3):
    """小文件直接 GET，带退避重试。"""
    last = None
    for i in range(tries):
        try:
            r = SESSION.get(url, timeout=TIMEOUT, verify=False)
            if r.status_code == 200:
                return r.content
            last = f'HTTP {r.status_code}'
        except requests.RequestException as e:
            last = str(e)[:80]
        time.sleep(2 * (i + 1))
    raise requests.RequestException(f'连续 {tries} 次失败: {last}')


def handle_hf_tree(src, args):
    repo = src['hf_repo']
    api = f'https://hf-mirror.com/api/datasets/{repo}'
    log(f'  列目录: {api}')
    r = SESSION.get(api, timeout=TIMEOUT)
    if r.status_code != 200:
        log(f'  [error] 列目录失败 HTTP {r.status_code}')
        return
    files = [s['rfilename'] for s in r.json().get('siblings', [])]
    is_voice = src['modality'] == 'voice'
    allowed = VOICE_EXTS if is_voice else IMAGE_EXTS + IMAGE_CONVERT_EXTS
    rule_labels = {l for _, l in src['rules'] if l != 'SKIP'}
    counts = {}
    idx = 0
    for rel in files:
        ext = os.path.splitext(rel.lower())[1]
        if ext not in allowed:
            continue
        label = match_rules(rel, src['rules'])
        if not label or label == 'SKIP':
            continue
        if args.max_files and counts.get(label, 0) >= args.max_files:
            if rule_labels <= {l for l in rule_labels if counts.get(l, 0) >= args.max_files}:
                break
            continue
        dst_dir = label_dir(src['modality'], label)
        stem = f"{src['id']}__{idx:07d}"
        idx += 1
        direct = is_voice or ext in IMAGE_EXTS
        dst = os.path.join(dst_dir, stem + ext if direct else stem + '.png')
        if os.path.exists(dst):
            counts[label] = counts.get(label, 0) + 1
            continue
        url = f'https://hf-mirror.com/datasets/{repo}/resolve/main/{rel}'
        try:
            data = fetch_bytes(url)
            if direct:
                with open(dst, 'wb') as f:
                    f.write(data)
            else:
                converted = convert_image_if_needed(data, dst_dir, stem, is_bytes=True)
                if not converted:
                    continue
        except Exception as e:
            log(f"    [warn] 失败 {rel[:70]}: {str(e)[:80]}")
            continue
        counts[label] = counts.get(label, 0) + 1
        if idx % 100 == 0:
            log(f'    进度 {idx}: {counts}')
    log(f'  归位完成: {counts}')
    for label, c in counts.items():
        audit(src['id'], label, c, {'license': src['license'], 'url': api})


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def run_source(src, args):
    log(f"\n[{src['id']}] {src['name']}")
    if src.get('requires'):
        missing = [m for m in src['requires'] if m not in sys.modules and
                   not __import__('importlib.util', fromlist=['util']).util.find_spec(m)]
        if missing:
            log(f"  [skip] 缺少依赖 {missing}（不自动安装，请手动 pip install）")
            return

    if src.get('special') == 'cocoai_parquet':
        handle_cocoai(src, args)
        return

    if src.get('special') == 'hf_tree':
        handle_hf_tree(src, args)
        return

    extract_dir = os.path.join(EXTRACT_ROOT, src['id'])
    done_flag = os.path.join(extract_dir, '.EXTRACTED')

    # 1) 下载
    archives = []
    for item in src['files']:
        dst = os.path.join(DL_DIR, item['fname'])
        if not os.path.exists(dst):
            log(f"  下载: {item['url']}")
            download_resume(item['url'], dst)
        else:
            log(f"  已存在，跳过下载: {item['fname']}")
        archives.append(dst)

    # 2) 解压（幂等）
    if not os.path.exists(done_flag):
        for a in archives:
            log(f"  解压: {os.path.basename(a)}")
            extract_archive(a, extract_dir)
        if src.get('nested_tgz'):
            expand_nested_tgz(extract_dir)
        open(done_flag, 'w').write(datetime.now(timezone.utc).isoformat())
    else:
        log('  已解压，跳过')

    # 3) 归位
    log('  归位到 raw/ 目录 …')
    counts = place_files(src, extract_dir, max_files=args.max_files, move=args.move)
    for label, c in sorted(counts.items()):
        log(f'    {src["modality"]}/raw/{label}/  += {c}')
        audit(src['id'], label, c,
              {'license': src['license'], 'url': src['files'][0]['url']})
    if not counts:
        log('    [warn] 没有匹配到任何文件，规则可能已失效，请检查解压目录结构')


def cmd_list():
    log('可用数据源（* = 大型源，需 --include-huge）:\n')
    for s in SOURCES:
        flag = '*' if s['huge'] else ' '
        log(f"{flag} {s['id']:<24} {s['modality']:<5} ~{s['size_mb']:>6} MB  {s['name']}")
        log(f"      {s['note']}")
    log(f"\n起步包: --start-image ({','.join(START_IMAGE)})  "
        f"--start-voice ({','.join(START_VOICE)})")


def cmd_verify(selected):
    log('链接探测（不下载）:\n')
    for s in selected:
        urls = [f['url'] for f in s.get('files', [])]
        if s.get('special') == 'cocoai_parquet':
            urls = [s['url_tpl'].format(part=p) for p in s['parts'][:1]]
        if s.get('special') == 'hf_tree':
            urls = [f"https://hf-mirror.com/api/datasets/{s['hf_repo']}"]
        for u in urls:
            ok, code, size, final = probe_url(u)
            tag = 'OK ' if ok else 'FAIL'
            sz = f'{size/1e6:.1f}MB' if size else '?'
            log(f"  [{tag}] {s['id']:<24} HTTP {code} {sz:>9}  {u[:80]}")


def select_sources(args):
    if args.only:
        ids = [x.strip() for x in args.only.split(',') if x.strip()]
        chosen = [by_id(i) for i in ids]
    elif args.start_image:
        chosen = [by_id(i) for i in START_IMAGE]
    elif args.start_voice:
        chosen = [by_id(i) for i in START_VOICE]
    else:
        chosen = [s for s in SOURCES if not s['huge']]
    if not args.include_huge:
        huge = [s['id'] for s in chosen if s['huge']]
        chosen = [s for s in chosen if not s['huge']]
        if huge:
            log(f'[info] 大型源已跳过: {huge}（确认要下请加 --include-huge）')
    return chosen


def main():
    requests.packages.urllib3.disable_warnings()
    p = argparse.ArgumentParser(description='反诈语音/图片公开数据集下载与归位')
    p.add_argument('--list', action='store_true', help='列出所有数据源')
    p.add_argument('--verify', action='store_true', help='仅探测链接可达性与大小')
    p.add_argument('--only', type=str, help='指定数据源 id，逗号分隔')
    p.add_argument('--start-image', action='store_true', help='图片起步包(CASIA v1+v2)')
    p.add_argument('--start-voice', action='store_true', help='语音起步包(LibriSpeech)')
    p.add_argument('--include-huge', action='store_true', help='放行 GB 级大型源')
    p.add_argument('--max-files', type=int, default=None,
                   help='每个源每个标签最多归位的文件数（试跑用）')
    p.add_argument('--cocoai-parts', type=int, default=1, help='COCOAI 下载分片数(每片~340MB)')
    p.add_argument('--move', action='store_true', help='归位时移动而非复制（节省空间，默认复制）')
    args = p.parse_args()

    if args.list:
        cmd_list()
        return

    selected = select_sources(args)
    if not selected:
        cmd_list()
        return

    if args.verify:
        cmd_verify(selected)
        return

    free_gb = shutil.disk_usage(DATA_DIR if os.path.exists(DATA_DIR) else AI_SERVICE_DIR).free / 1e9
    need_gb = sum(s['size_mb'] for s in selected) / 1024
    log(f'本次数据源: {[s["id"] for s in selected]}')
    log(f'归档体积约 {need_gb:.2f} GB，当前盘剩余 {free_gb:.1f} GB，下载目录: {DL_DIR}')
    if free_gb < need_gb * 1.3:
        log('[warn] 磁盘空间可能不足，请清理后重试（可先用 --max-files 小规模试跑）')

    for s in selected:
        try:
            run_source(s, args)
        except Exception as e:
            log(f'[error] 源 {s["id"]} 失败: {type(e).__name__}: {e}')
            log('        可直接重跑本脚本，已完成部分会自动跳过/续传。')

    log('\n全部处理结束。下一步：')
    if any(s['modality'] == 'voice' for s in selected):
        log('  python scripts/preprocess_voice.py')
    if any(s['modality'] == 'image' for s in selected):
        log('  python scripts/preprocess_image.py')


if __name__ == '__main__':
    main()
