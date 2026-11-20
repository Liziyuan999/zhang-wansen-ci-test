# -*- coding: utf-8 -*-
"""冒烟测试：验证应用可导入、15 张表、注册/登录/文档/RAG/Agent 基础流程。"""
import io
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.db.base import Base  # noqa: E402

client = TestClient(app)

PASS = 0
FAIL = 0


def check(name: str, cond: bool, extra: str = ""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"PASS | {name}")
    else:
        FAIL += 1
        print(f"FAIL | {name} {extra}")


def main() -> None:
    # TestClient 默认不触发 lifespan，这里显式建表
    from app.db.session import engine as _engine

    Base.metadata.create_all(bind=_engine)

    # 1. 表数量
    expected = {
        "user", "refresh_token", "email_code", "department",
        "document", "doc_tag", "doc_tag_rel", "doc_chunk",
        "conversation", "conversation_msg", "feedback",
        "agent_task", "operation_log", "llm_call_log", "sys_config",
    }
    tables = set(Base.metadata.tables.keys())
    check("15张ORM表已注册", tables == expected, f"got={sorted(tables)}")

    # 2. 健康检查
    r = client.get("/api/health")
    check("健康检查", r.status_code == 200 and r.json()["code"] == 0)

    # 3. 注册：发送验证码 -> 注册（每次用唯一邮箱避免发送间隔限制）
    email = f"smoke{int(time.time())}@knowseek.com"
    r = client.post("/api/auth/send-code", json={"email": email, "purpose": "register"})
    check("发送注册验证码", r.status_code == 200 and r.json()["code"] == 0, r.text)

    from app.services.email import generate_code
    from app.services.email import _hash_code
    from app.db.session import SessionLocal
    from app.models import EmailCode
    db = SessionLocal()
    rec = db.query(EmailCode).filter(EmailCode.email == email, EmailCode.purpose == "register").order_by(EmailCode.create_time.desc()).first()
    code_ok = rec is not None
    check("验证码已入库", code_ok)
    if code_ok:
        # 从哈希无法反解，直接标记使用并改库内哈希为已知值模拟（仅冒烟用）
        db.query(EmailCode).filter(EmailCode.id == rec.id).update({"code_hash": _hash_code("123456")})
        db.commit()
    db.close()

    r = client.post(
        "/api/auth/register",
        json={"email": email, "code": "123456", "username": f"smoke_user{int(time.time())}", "password": "pass123456", "dept_name": "冒烟测试部"},
    )
    reg = r.json()
    check("注册成功并返回双token", reg["code"] == 0 and "access_token" in reg["data"] and "refresh_token" in reg["data"], r.text)
    access = reg["data"]["access_token"]
    headers = {"Authorization": f"Bearer {access}"}

    # 4. me
    r = client.get("/api/auth/me", headers=headers)
    check("获取当前用户", r.json()["code"] == 0 and r.json()["data"]["email"] == email)

    # 5. 上传文档 -> 解析 -> 列表
    content = "企业知识库建设方案：本项目旨在打造企业级智能知识中枢，支持文档管理、智能问答与Agent自动化。目标部门包含研发部与市场部，重点提升知识复用效率。"
    files = {"file": ("方案.txt", io.BytesIO(content.encode("utf-8")), "text/plain")}
    r = client.post("/api/documents/upload", files=files, headers=headers)
    check("上传文档", r.json()["code"] == 0, r.text)
    doc_id = r.json()["data"]["id"]

    # BackgroundTasks 在 TestClient 中同步执行完毕
    r = client.get(f"/api/documents/{doc_id}", headers=headers)
    detail = r.json()["data"]
    check("文档解析完成", detail["status"] == "success", f"status={detail.get('status')} fail={detail.get('fail_msg')}")

    # 6. 标签
    r = client.post(f"/api/documents/{doc_id}/tags", json={"tag_names": ["方案", "知识库"]}, headers=headers)
    check("文档打标签", r.json()["code"] == 0)

    # 7. RAG 对话（SSE）
    with client.stream("POST", "/api/chat/ask", json={"question": "这个方案的目标是什么？"}, headers=headers) as resp:
        body = resp.read().decode("utf-8")
        check("SSE 返回溯源事件", "citations" in body and "done" in body, body[:300])
        check("SSE 返回流式回答", "delta" in body, body[:300])

    # 8. Agent 任务创建 + 确认
    r = client.post("/api/agent/tasks", json={"task_type": "doc_compare", "doc_ids": [doc_id]}, headers=headers)
    task = r.json()
    check("Agent任务创建并等待确认", task["code"] == 0 and task["data"]["need_confirm"] is True, r.text)
    task_id = task["data"]["task_id"]
    r = client.post(f"/api/agent/tasks/{task_id}/confirm", json={"confirm": True}, headers=headers)
    check("Agent人工确认生成结果", r.json()["code"] == 0 and r.json()["data"]["status"] == "finished", r.text)

    # 9. 管理员登录
    r = client.post("/api/auth/login", json={"email": "smoke@knowseek.com", "code": "123456"})
    # 先发送登录验证码
    client.post("/api/auth/send-code", json={"email": email, "purpose": "login"})
    db = SessionLocal()
    rec2 = db.query(EmailCode).filter(EmailCode.email == email, EmailCode.purpose == "login").order_by(EmailCode.create_time.desc()).first()
    if rec2:
        db.query(EmailCode).filter(EmailCode.id == rec2.id).update({"code_hash": _hash_code("123456")})
        db.commit()
    db.close()
    r = client.post("/api/auth/login", json={"email": email, "code": "123456"})
    check("验证码登录成功", r.json()["code"] == 0, r.text)

    print(f"\n===== 结果: PASS={PASS} FAIL={FAIL} =====")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
