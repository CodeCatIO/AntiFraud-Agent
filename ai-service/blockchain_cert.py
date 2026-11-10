#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
区块链存证模块 (blockchain_cert.py)
=====================================
用途：模拟区块链存证功能，对数据进行SHA-256哈希并存入本地链文件
调用方式：
    存证：python blockchain_cert.py certify "数据内容"
    验证：python blockchain_cert.py verify "哈希值"
输出：JSON格式到stdout
链文件保存在 python/blockchain_data/ 目录下
"""

import sys
import json
import os
import hashlib
from datetime import datetime


# 链文件目录
BLOCKCHAIN_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blockchain_data")
CHAIN_FILE = os.path.join(BLOCKCHAIN_DATA_DIR, "chain.json")


def ensure_data_dir():
    """确保区块链数据目录存在"""
    os.makedirs(BLOCKCHAIN_DATA_DIR, exist_ok=True)


def load_chain():
    """
    加载区块链数据

    Returns:
        list: 区块链数据列表
    """
    ensure_data_dir()
    if os.path.exists(CHAIN_FILE):
        try:
            with open(CHAIN_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def save_chain(chain):
    """
    保存区块链数据

    Args:
        chain: 区块链数据列表
    """
    ensure_data_dir()
    with open(CHAIN_FILE, 'w', encoding='utf-8') as f:
        json.dump(chain, f, ensure_ascii=False, indent=2)


def compute_hash(data):
    """
    计算SHA-256哈希值

    Args:
        data: 要哈希的数据

    Returns:
        str: 十六进制哈希值
    """
    if isinstance(data, str):
        data = data.encode('utf-8')
    return hashlib.sha256(data).hexdigest()


def create_genesis_block():
    """
    创建创世区块

    Returns:
        dict: 创世区块
    """
    return {
        "index": 0,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data": "Genesis Block",
        "hash": compute_hash("Genesis Block"),
        "previous_hash": "0"
    }


def certify(data_content):
    """
    对数据进行存证

    Args:
        data_content: 要存证的数据内容

    Returns:
        dict: 存证结果
    """
    try:
        # 加载链
        chain = load_chain()

        # 如果链为空，创建创世区块
        if len(chain) == 0:
            genesis = create_genesis_block()
            chain.append(genesis)

        # 计算数据哈希
        data_hash = compute_hash(data_content)

        # 检查是否已存在相同哈希
        for block in chain:
            if block.get("hash") == data_hash:
                return {
                    "success": True,
                    "hash": data_hash,
                    "block_index": block["index"],
                    "timestamp": block["timestamp"],
                    "detail": "数据已存在存证记录，无需重复存证"
                }

        # 获取前一区块哈希
        previous_hash = chain[-1]["hash"]

        # 创建新区块
        new_block = {
            "index": len(chain),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data": data_content,
            "hash": data_hash,
            "previous_hash": previous_hash
        }

        # 添加到链
        chain.append(new_block)

        # 保存链
        save_chain(chain)

        return {
            "success": True,
            "hash": data_hash,
            "block_index": new_block["index"],
            "timestamp": new_block["timestamp"],
            "detail": "存证成功"
        }

    except Exception as e:
        return {
            "success": False,
            "hash": "",
            "block_index": -1,
            "timestamp": "",
            "detail": f"存证失败: {str(e)}"
        }


def verify(hash_value):
    """
    验证哈希是否在链中存在

    Args:
        hash_value: 要验证的哈希值

    Returns:
        dict: 验证结果
    """
    try:
        # 加载链
        chain = load_chain()

        if len(chain) == 0:
            return {
                "exists": False,
                "block_index": -1,
                "timestamp": "",
                "detail": "区块链为空，无存证记录"
            }

        # 如果输入不是哈希格式，先计算哈希
        if len(hash_value) != 64:
            hash_value = compute_hash(hash_value)

        # 在链中查找
        for block in chain:
            if block.get("hash") == hash_value:
                return {
                    "exists": True,
                    "block_index": block["index"],
                    "timestamp": block["timestamp"],
                    "detail": "验证通过，数据已存证"
                }

        return {
            "exists": False,
            "block_index": -1,
            "timestamp": "",
            "detail": "验证失败，数据未在链中存证"
        }

    except Exception as e:
        return {
            "exists": False,
            "block_index": -1,
            "timestamp": "",
            "detail": f"验证异常: {str(e)}"
        }


def main():
    try:
        if len(sys.argv) < 3:
            result = {
                "success": False,
                "detail": "参数不足，用法: python blockchain_cert.py certify/verify 数据内容或哈希值"
            }
            print(json.dumps(result, ensure_ascii=False))
            return

        mode = sys.argv[1].lower()

        if mode == "certify":
            data_content = sys.argv[2]
            result = certify(data_content)
            print(json.dumps(result, ensure_ascii=False))

        elif mode == "verify":
            hash_or_data = sys.argv[2]
            result = verify(hash_or_data)
            print(json.dumps(result, ensure_ascii=False))

        else:
            result = {
                "success": False,
                "detail": f"不支持的模式: {mode}，请使用 certify 或 verify"
            }
            print(json.dumps(result, ensure_ascii=False))

    except Exception as e:
        error_result = {
            "success": False,
            "detail": f"区块链存证异常: {str(e)}"
        }
        print(json.dumps(error_result, ensure_ascii=False), file=sys.stderr)


if __name__ == "__main__":
    main()
