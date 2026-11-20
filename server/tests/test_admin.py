# -*- coding: utf-8 -*-
"""管理员后台与 seed 数据验证。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.db.base import Base  # noqa: E402

Base.metadata.create_all(bind=engine)

client = TestClient(app)
ok_count = 0
fail_count = 0


def check(name: str, cond: bool, extra: str = ""):
    global ok_count, fail_count
    print(("PASS | " if cond else "FAIL | ") + name + (" " + extra if extra else ""))
    if cond:
        ok_count += 1
    else:
        fail_count += 1


# 1. 初始化种子数据（默认部门 + 管理员）
import subprocess
r = subprocess.run([sys.executable, str(Path(__file__).resolve().parent.parent / "scripts" / "seed_data.py")], capture_output=True, text=True, encoding="utf-8")
check("seed_data 脚本执行", r.returncode == 0, r.stdout[-200:] + r.stderr[-200:])

# 2. 管理员登录（验证码登录）
admin_email = "admin@knowseek.com"
from app.services.email import _hash_code
from app.db.session import SessionLocal
from app.models import EmailCode
db = SessionLocal()
# 清空旧验证码，避免发送间隔与已用状态干扰
db.query(EmailCode).filter(EmailCode.email == admin_email).delete()
db.commit()
db.close()
client.post("/api/auth/send-code", json={"email": admin_email, "purpose": "login"})
db = SessionLocal()
rec = db.query(EmailCode).filter(EmailCode.email == admin_email, EmailCode.purpose == "login").order_by(EmailCode.create_time.desc()).first()
if rec:
    db.query(EmailCode).filter(EmailCode.id == rec.id).update({"code_hash": _hash_code("123456")})
    db.commit()
db.close()
r = client.post("/api/auth/login", json={"email": admin_email, "code": "123456"})
j = r.json()
check("管理员登录", j["code"] == 0, r.text[:300])
if j["code"] == 0:
    headers = {"Authorization": f"Bearer {j['data']['access_token']}"}
    check("管理员角色", j["data"]["user"]["role"] == "admin")

    # 3. 后台：用户列表 / 部门列表 / 日志 / LLM 记录 / 配置
    r = client.get("/api/admin/users", headers=headers)
    check("后台用户列表", r.json()["code"] == 0 and r.json()["data"]["total"] >= 1, r.text[:200])
    r = client.get("/api/admin/departments", headers=headers)
    check("后台部门列表", r.json()["code"] == 0 and len(r.json()["data"]) >= 1, r.text[:200])
    r = client.get("/api/admin/logs", headers=headers)
    check("后台审计日志", r.json()["code"] == 0, r.text[:200])
    r = client.get("/api/admin/llm-logs", headers=headers)
    check("后台LLM记录", r.json()["code"] == 0, r.text[:200])
    r = client.get("/api/admin/configs", headers=headers)
    check("后台配置列表", r.json()["code"] == 0, r.text[:200])

    # 4. 普通用户访问后台应被拒绝
    from app.models import User
    from app.services.email import _hash_code
    db = SessionLocal()
    staff = db.query(User).filter(User.role == "staff").first()
    db.close()
    if staff:
        # 用员工账号走验证码登录，再访问后台接口，应被 10003 拒绝
        staff_email = staff.email
        db = SessionLocal()
        db.query(EmailCode).filter(EmailCode.email == staff_email).delete()
        db.commit()
        db.close()
        client.post("/api/auth/send-code", json={"email": staff_email, "purpose": "login"})
        db = SessionLocal()
        rec = db.query(EmailCode).filter(EmailCode.email == staff_email, EmailCode.purpose == "login").order_by(EmailCode.create_time.desc()).first()
        if rec:
            db.query(EmailCode).filter(EmailCode.id == rec.id).update({"code_hash": _hash_code("123456")})
            db.commit()
        db.close()
        r = client.post("/api/auth/login", json={"email": staff_email, "code": "123456"})
        sj = r.json()
        if sj["code"] == 0:
            staff_headers = {"Authorization": f"Bearer {sj['data']['access_token']}"}
            r = client.get("/api/admin/users", headers=staff_headers)
            check("普通用户访问后台被拒绝", r.json()["code"] == 10003, r.text[:200])
        else:
            check("员工账号登录（前置条件）", False, r.text[:200])
    else:
        print("SKIP | 无 staff 用户，跳过越权校验（首次部署可先注册员工账号）")

    # 5. 刷新 token
    r = client.post("/api/auth/refresh", json={"refresh_token": j["data"]["refresh_token"]})
    check("刷新token", r.json()["code"] == 0 and r.json()["data"]["access_token"], r.text[:200])

print(f"\n===== 结果: PASS={ok_count} FAIL={fail_count} =====")
sys.exit(1 if fail_count else 0)
