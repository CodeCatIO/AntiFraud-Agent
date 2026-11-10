# -*- coding: utf-8 -*-
"""临时脚本：经 Spring Boot 9090 全链路复测语音/图片检测并验证落库。"""
import os, time, requests

B = "http://localhost:9090"
HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(os.path.dirname(HERE))  # ai-service


def login_retry(n=6):
    for i in range(n):
        r = requests.post(B + "/user/login",
                          json={"username": "user", "password": "123456"}, timeout=15)
        j = r.json()
        if j.get("data") and j["data"].get("token"):
            return j["data"]["token"]
        time.sleep(2)
    raise RuntimeError("登录多次失败: " + r.text[:200])


def upload(api, rel, label):
    path = os.path.join(BASE, rel)
    with open(path, "rb") as f:
        r = requests.post(B + api,
                          files={"file": (os.path.basename(path), f)},
                          headers={"token": token}, timeout=120)
    j = r.json()
    print(f"[{label}] HTTP {r.status_code} code={j.get('code')}")
    d = j.get("data") or {}
    print(f"  recordId={d.get('recordId')}  level={d.get('riskLevel')}  score={d.get('riskScore')}")
    detail = d.get("detail")
    if isinstance(detail, dict):
        print("  detail:", str(detail.get('detail'))[:110])
    else:
        print("  detail:", str(detail)[:110])


token = login_retry()
print("login ok, token len =", len(token))
time.sleep(2)
upload("/detect/voice", os.path.join("data", "manual_test", "robot_flat_tone.wav"), "9090 voice robot-tone")
time.sleep(2)
upload("/detect/image", os.path.join("data", "multimodal", "cases", "case_0000", "image.png"), "9090 image case_0000")
