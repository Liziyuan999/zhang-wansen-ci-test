"""真实后端 SSE 连接验证：注册用户 -> 建立 SSE -> 读两帧。"""
import io
import json
import time
import urllib.request

BASE = "http://127.0.0.1:8000"
ts = int(time.time())


def post_json(path, payload, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def get_json(path, token=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE + path, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


# 1. 注册用户拿 token
email = f"sse{ts}@knowseek.com"
post_json("/api/auth/send-code", {"email": email})

import sys

sys.path.insert(0, r"E:\AI-Agent知识库\server")
from app.services.email import _hash_code  # noqa: E402

import sqlite3

db = sqlite3.connect(r"E:\AI-Agent知识库\server\ai_assistant.db")
db.execute(
    "UPDATE email_code SET code_hash=? WHERE email=? AND purpose='register'",
    (_hash_code("123456"), email),
)
db.commit()
db.close()
reg = post_json("/api/auth/register", {"email": email, "code": "123456", "password": "pass1234", "username": f"sseuser{ts % 100000}", "name": f"SSE用户{ts % 1000}", "dept_name": "SSE验证部"})
print("REGISTER:", reg.get("code"), reg.get("message"))
token = reg["data"]["access_token"]

# 2. 建立 SSE 连接读两帧（最多 12s）
req = urllib.request.Request(BASE + "/api/notice/events?token=" + token, method="GET")
resp = urllib.request.urlopen(req, timeout=12)
print("STATUS:", resp.status, resp.headers.get("content-type"))
frames = []
deadline = time.time() + 10
try:
    while time.time() < deadline:
        line = resp.readline().decode("utf-8", "ignore").strip()
        if line.startswith("data:"):
            frames.append(line[5:].strip())
            print("FRAME:", line[:120])
            if len(frames) >= 2:
                break
    print("SSE OK" if frames else "SSE EMPTY")
except Exception as e:  # noqa: BLE001
    print("SSE ERR:", e)
resp.close()
