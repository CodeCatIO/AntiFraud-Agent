#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数字水印嵌入与提取模块 (watermark.py)
=====================================
用途：使用LSB（最低有效位）隐写术在图片中嵌入或提取数字水印
调用方式：
    嵌入水印：python watermark.py embed "图片路径" "水印文本"
    提取水印：python watermark.py extract "图片路径"
输出：JSON格式到stdout
依赖：Pillow, numpy
"""

import sys
import json
import os


def text_to_bits(text):
    """
    将文本转换为二进制位列表

    Args:
        text: 要转换的文本

    Returns:
        list: 二进制位列表
    """
    # 先写入长度信息（32位），再写入文本内容
    text_bytes = text.encode('utf-8')
    length_bits = format(len(text_bytes), '032b')
    text_bits = ''.join(format(byte, '08b') for byte in text_bytes)
    return [int(b) for b in length_bits + text_bits]


def bits_to_text(bits):
    """
    将二进制位列表转换回文本

    Args:
        bits: 二进制位列表

    Returns:
        str: 转换后的文本，或None（如果失败）
    """
    try:
        # 前32位是长度信息
        if len(bits) < 32:
            return None

        length_bits = bits[:32]
        length = int(''.join(str(b) for b in length_bits), 2)

        # 检查长度是否合理
        if length <= 0 or length * 8 + 32 > len(bits):
            return None

        # 提取文本位
        text_bits = bits[32:32 + length * 8]
        text_bytes = bytearray()
        for i in range(0, len(text_bits), 8):
            byte_bits = text_bits[i:i+8]
            if len(byte_bits) < 8:
                break
            byte_val = int(''.join(str(b) for b in byte_bits), 2)
            text_bytes.append(byte_val)

        return text_bytes.decode('utf-8')
    except Exception:
        return None


def embed_watermark(image_path, watermark_text, output_path=None):
    """
    使用LSB隐写术在图片中嵌入水印

    Args:
        image_path: 原始图片路径
        watermark_text: 要嵌入的水印文本
        output_path: 输出图片路径（可选，默认在原文件名后加_watermarked）

    Returns:
        dict: 嵌入结果
    """
    try:
        from PIL import Image
        import numpy as np

        # 检查文件是否存在
        if not os.path.exists(image_path):
            return {
                "success": False,
                "output_path": "",
                "detail": f"图片文件不存在: {image_path}"
            }

        # 打开图片
        img = Image.open(image_path)
        img = img.convert('RGB')

        # 生成输出路径
        if output_path is None:
            base, ext = os.path.splitext(image_path)
            output_path = f"{base}_watermarked.png"

        # 转换为numpy数组
        img_array = np.array(img)

        # 将水印转换为二进制位
        watermark_bits = text_to_bits(watermark_text)

        # 计算可用的LSB位数（每个像素3个通道，每个通道1个LSB位）
        total_pixels = img_array.shape[0] * img_array.shape[1]
        available_bits = total_pixels * 3

        if len(watermark_bits) > available_bits:
            return {
                "success": False,
                "output_path": "",
                "detail": "水印数据过大，超出图片容量"
            }

        # 嵌入水印到LSB
        bit_index = 0
        for i in range(img_array.shape[0]):
            for j in range(img_array.shape[1]):
                for k in range(3):  # R, G, B三个通道
                    if bit_index < len(watermark_bits):
                        # 将最低有效位替换为水印位
                        img_array[i, j, k] = (img_array[i, j, k] & 0xFE) | watermark_bits[bit_index]
                        bit_index += 1
                    else:
                        break
                if bit_index >= len(watermark_bits):
                    break
            if bit_index >= len(watermark_bits):
                break

        # 保存图片（使用PNG格式，无损）
        watermarked_img = Image.fromarray(img_array.astype('uint8'), 'RGB')
        watermarked_img.save(output_path, 'PNG')

        return {
            "success": True,
            "output_path": os.path.abspath(output_path),
            "detail": "水印嵌入成功"
        }

    except ImportError:
        return {
            "success": False,
            "output_path": "",
            "detail": "缺少依赖库Pillow，无法嵌入水印"
        }
    except Exception as e:
        return {
            "success": False,
            "output_path": "",
            "detail": f"水印嵌入失败: {str(e)}"
        }


def extract_watermark(image_path):
    """
    从图片中提取LSB隐写的水印信息

    Args:
        image_path: 含水印图片路径

    Returns:
        dict: 提取结果
    """
    try:
        from PIL import Image
        import numpy as np

        # 检查文件是否存在
        if not os.path.exists(image_path):
            return {
                "success": False,
                "watermark": "",
                "detail": f"图片文件不存在: {image_path}"
            }

        # 打开图片
        img = Image.open(image_path)
        img = img.convert('RGB')

        # 转换为numpy数组
        img_array = np.array(img)

        # 提取LSB位
        bits = []
        # 先提取前32位（长度信息）+ 足够多的位用于文本
        max_bits = min(img_array.shape[0] * img_array.shape[1] * 3, 100000)  # 限制最大提取位数

        bit_index = 0
        for i in range(img_array.shape[0]):
            for j in range(img_array.shape[1]):
                for k in range(3):
                    if bit_index < max_bits:
                        bits.append(img_array[i, j, k] & 1)
                        bit_index += 1
                    else:
                        break
                if bit_index >= max_bits:
                    break
            if bit_index >= max_bits:
                break

        # 将位转换回文本
        watermark = bits_to_text(bits)

        if watermark is not None:
            return {
                "success": True,
                "watermark": watermark,
                "detail": "水印提取成功"
            }
        else:
            return {
                "success": False,
                "watermark": "",
                "detail": "未检测到有效水印信息"
            }

    except ImportError:
        return {
            "success": False,
            "watermark": "",
            "detail": "缺少依赖库Pillow，无法提取水印"
        }
    except Exception as e:
        return {
            "success": False,
            "watermark": "",
            "detail": f"水印提取失败: {str(e)}"
        }


def main():
    try:
        if len(sys.argv) < 3:
            result = {
                "success": False,
                "detail": "参数不足，用法: python watermark.py embed/extract 图片路径 [水印文本]"
            }
            print(json.dumps(result, ensure_ascii=False))
            return

        mode = sys.argv[1].lower()

        if mode == "embed":
            if len(sys.argv) < 4:
                result = {
                    "success": False,
                    "detail": "嵌入模式需要提供水印文本，用法: python watermark.py embed 图片路径 水印文本"
                }
                print(json.dumps(result, ensure_ascii=False))
                return
            image_path = sys.argv[2]
            watermark_text = sys.argv[3]
            result = embed_watermark(image_path, watermark_text)
            print(json.dumps(result, ensure_ascii=False))

        elif mode == "extract":
            image_path = sys.argv[2]
            result = extract_watermark(image_path)
            print(json.dumps(result, ensure_ascii=False))

        else:
            result = {
                "success": False,
                "detail": f"不支持的模式: {mode}，请使用 embed 或 extract"
            }
            print(json.dumps(result, ensure_ascii=False))

    except Exception as e:
        error_result = {
            "success": False,
            "detail": f"水印操作异常: {str(e)}"
        }
        print(json.dumps(error_result, ensure_ascii=False), file=sys.stderr)


if __name__ == "__main__":
    main()
