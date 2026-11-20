# -*- coding: utf-8 -*-
"""组织中心升级冒烟测试：共享知识库 / 下载审批 / 退出审批 / 企业打卡 / 通知中心 / SSE / 审计。

覆盖接口：
- 团队创建/邀请/接受（team.py）
- 共享知识库列表/详情（org_extra.py）
- 下载申请/审批/审批后下载（org_extra.py）
- 退出申请/审批/成员移除（org_extra.py）
- 企业打卡 clock-in/clock-out/today/my（org_extra.py）
- 通知中心 list/unread-count/read（notice.py）
- 通知 SSE events（notice.py）
- 审计 operation_log（services.audit）
"""
import io
import sys
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


def register_user(email: str, username: str) -> str:
    """注册并返回 access_token（复用 test_smoke 的验证码注入手法）。"""
    from app.services.email import _hash_code, generate_code
    from app.db.session import SessionLocal
    from app.models import EmailCode

    r = client.post("/api/auth/send-code", json={"email": email, "purpose": "register"})
    assert r.status_code == 200 and r.json()["code"] == 0, r.text
    db = SessionLocal()
    rec = (
        db.query(EmailCode)
        .filter(EmailCode.email == email, EmailCode.purpose == "register")
        .order_by(EmailCode.create_time.desc())
        .first()
    )
    assert rec is not None, "验证码未入库"
    db.query(EmailCode).filter(EmailCode.id == rec.id).update({"code_hash": _hash_code("123456")})
    db.commit()
    db.close()
    r = client.post(
        "/api/auth/register",
        json={"email": email, "code": "123456", "username": username, "password": "pass123456", "dept_name": "冒烟测试部"},
    )
    body = r.json()
    assert body["code"] == 0 and "access_token" in body["data"], r.text
    return body["data"]["access_token"]


def main() -> None:
    from app.db.session import engine as _engine

    Base.metadata.create_all(bind=_engine)

    ts = int(time.time())
    owner_email = f"owner{ts}@knowseek.com"
    member_email = f"member{ts}@qq.com"
    owner_token = register_user(owner_email, f"owner_{ts % 100000}")
    member_token = register_user(member_email, f"member_{ts % 100000}")
    oh = {"Authorization": f"Bearer {owner_token}"}
    mh = {"Authorization": f"Bearer {member_token}"}

    # ---------- A. 建团队 + 邀请 + 成员加入 ----------
    r = client.post("/api/team/create", json={"name": f"冒烟团队{ts % 1000}", "description": "组织中心冒烟"}, headers=oh)
    team_id = r.json()["data"]["id"]
    check("创建团队", r.json()["code"] == 0, r.text)

    content = f"团队共享知识库文档{ts}：企业知识库建设方案，含研发部与市场部知识复用目标，支持下载审批流验证。"
    files = {"file": (f"共享方案{ts}.txt", io.BytesIO(content.encode("utf-8")), "text/plain")}
    r = client.post("/api/documents/upload", files=files, headers=oh)
    body = r.json()
    check("所有者上传共享文档", body["code"] == 0, r.text)
    doc_id = body["data"]["id"]
    r = client.get(f"/api/documents/{doc_id}", headers=oh)
    check("共享文档解析完成", r.json()["data"]["status"] == "success", f"status={r.json()['data'].get('status')}")

    r = client.post(f"/api/team/{team_id}/invite", json={"qq_email": member_email}, headers=oh)
    inv = r.json()["data"]
    check("所有者邀请成员", r.json()["code"] == 0, r.text)
    token = inv["token"]

    r = client.post(f"/api/team/invite/{token}/accept", headers=mh)
    check("成员接受邀请加入团队", r.json()["code"] == 0, r.text)

    # ---------- B. 共享知识库 + 下载审批流 ----------
    r = client.get(f"/api/team/{team_id}/shared-docs", headers=mh)
    items = r.json()["data"]["items"]
    check("成员可见共享知识库列表", r.json()["code"] == 0 and len(items) == 1, f"items={len(items)}")

    r = client.get(f"/api/team/{team_id}/shared-docs/{doc_id}", headers=mh)
    check("成员可见共享文档详情", r.json()["code"] == 0 and "共享方案" in r.json()["data"]["doc_name"], r.text)

    r = client.post(f"/api/team/{team_id}/shared-docs/{doc_id}/download-request?reason=冒烟测试下载", headers=mh)
    ap = r.json()["data"]
    check("成员提交下载申请(pending)", r.json()["code"] == 0 and ap["status"] == "pending", r.text)
    dl_ap_id = ap["id"]

    r = client.post(
        f"/api/team/{team_id}/shared-docs/{doc_id}/download-request?reason=重复提交", headers=mh
    )
    check("重复下载申请被拦截", r.json()["code"] != 0, r.text)

    r = client.get(f"/api/team/{team_id}/approvals/pending-count", headers=oh)
    pc = r.json()["data"]
    check("所有者待审批计数含下载申请", pc["downloads"] >= 1 and pc["total"] >= 1, f"pc={pc}")

    r = client.get(f"/api/team/{team_id}/approvals/downloads?status=pending", headers=oh)
    check("所有者可见下载审批列表", r.json()["code"] == 0 and r.json()["data"]["total"] >= 1, r.text)

    r = client.post(f"/api/team/{team_id}/approvals/downloads/{dl_ap_id}/approve", headers=oh)
    check("所有者审批通过下载申请", r.json()["code"] == 0 and r.json()["data"]["status"] == "approved", r.text)

    r = client.post(f"/api/team/{team_id}/approvals/downloads/{dl_ap_id}/approve", headers=oh)
    check("重复审批被拦截", r.json()["code"] != 0, r.text)

    r = client.get(f"/api/team/{team_id}/shared-docs/{doc_id}/download?approval_id={dl_ap_id}", headers=mh)
    check("成员审批通过后可下载", r.status_code == 200 and "application" not in r.headers.get("content-type", "json").lower(), f"ct={r.headers.get('content-type')}")

    # 未审批的文档（新上传一份供越权测试）
    files2 = {"file": (f"第二份{ts}.txt", io.BytesIO(f"另一份未审批文档{ts}".encode("utf-8")), "text/plain")}
    r = client.post("/api/documents/upload", files=files2, headers=oh)
    body2 = r.json()
    check("上传第二份文档(越权测试用)", body2["code"] == 0, r.text)
    doc2 = body2["data"]["id"]
    r = client.get(f"/api/team/{team_id}/shared-docs/{doc2}/download", headers=mh)
    check("无审批记录下载被拒绝", r.json()["code"] != 0, r.text)

    # 成员视角我的申请
    r = client.get(f"/api/team/{team_id}/approvals/my", headers=mh)
    my = r.json()["data"]
    check("成员我的申请含下载记录", r.json()["code"] == 0 and len(my["downloads"]) >= 1, r.text)

    # ---------- D. 通知中心 ----------
    r = client.get("/api/notice/unread-count", headers=mh)
    before = r.json()["data"]["count"]
    check("成员有未读通知(审批已通过)", before >= 1, f"count={before}")

    r = client.get("/api/notice/list?category=approval&page=1&page_size=20", headers=mh)
    nlist = r.json()["data"]
    check("成员通知列表按审批分类可查", r.json()["code"] == 0 and nlist["total"] >= 1, r.text)
    first_nid = nlist["items"][0]["id"]

    r = client.post(f"/api/notice/{first_nid}/read", headers=mh)
    check("单条通知标记已读", r.json()["code"] == 0, r.text)
    r = client.get("/api/notice/unread-count", headers=mh)
    after = r.json()["data"]["count"]
    check("已读后未读数减一", after == before - 1, f"before={before} after={after}")

    r = client.get("/api/notice/list?category=team", headers=mh)
    counts = r.json()["data"]["category_counts"]
    check("通知分类计数返回", r.json()["code"] == 0 and "team" in counts, r.text)

    # ---------- C. 企业打卡 ----------
    r = client.post(f"/api/team/{team_id}/attendance/clock-in", headers=oh)
    check("上班打卡", r.json()["code"] == 0 and r.json()["data"]["clock_in_time"], r.text)
    r = client.post(f"/api/team/{team_id}/attendance/clock-in", headers=oh)
    check("重复上班打卡被拦截", r.json()["code"] != 0, r.text)
    r = client.post(f"/api/team/{team_id}/attendance/clock-out", headers=oh)
    check("下班打卡", r.json()["code"] == 0 and r.json()["data"]["clock_out_time"], r.text)
    r = client.get(f"/api/team/{team_id}/attendance/today", headers=oh)
    today = r.json()["data"]
    check("今日打卡状态", today["my"]["status"] == "out" and today["stats"]["member_count"] >= 1, r.text)
    r = client.get(f"/api/team/{team_id}/attendance/my", headers=oh)
    check("我的打卡记录", r.json()["code"] == 0 and len(r.json()["data"]["items"]) >= 1, r.text)

    # ---------- E. 退出团队审批 ----------
    r = client.post(f"/api/team/{team_id}/approvals/exits?reason=个人原因退出", headers=mh)
    exit_ap = r.json()["data"]
    check("成员提交退出申请(pending)", r.json()["code"] == 0 and exit_ap["status"] == "pending", r.text)
    exit_id = exit_ap["id"]

    r = client.get(f"/api/team/{team_id}/approvals/pending-count", headers=oh)
    pc2 = r.json()["data"]
    check("所有者待审批计数含退出申请", pc2["exits"] >= 1, f"pc2={pc2}")

    r = client.post(f"/api/team/{team_id}/approvals/exits/{exit_id}/approve", headers=oh)
    check("所有者审批通过退出申请", r.json()["code"] == 0 and r.json()["data"]["status"] == "approved", r.text)

    r = client.get(f"/api/team/{team_id}", headers=oh)
    members = r.json()["data"]["members"]
    member_ids = [m["user_id"] for m in members]
    check("审批通过后成员被移除", r.json()["code"] == 0 and len(members) == 1, f"members={len(members)}")

    r = client.get(f"/api/team/{team_id}/shared-docs", headers=mh)
    check("已退出成员访问共享库被拒绝", r.json()["code"] != 0, r.text)

    # ---------- G. 通知 SSE ----------
    import threading

    sse_result: dict = {"ok": False, "detail": ""}

    def _read_sse():
        try:
            with client.stream("GET", f"/api/notice/events?token={member_token}") as resp:
                got: list[str] = []
                for chunk in resp.iter_bytes():
                    got.append(chunk.decode("utf-8", "ignore"))
                    if len(got) >= 2:
                        break
                sse_result["ok"] = resp.status_code == 200 and any("data:" in g for g in got)
                sse_result["detail"] = f"status={resp.status_code} frames={got[:2]}"
        except Exception as e:  # noqa: BLE001
            sse_result["detail"] = f"err={e}"

    t = threading.Thread(target=_read_sse, daemon=True)
    t.start()
    t.join(timeout=20)
    if t.is_alive():
        sse_result["detail"] = "sse read timeout(20s)"
    check("通知 SSE 长连接可建立并收到帧", sse_result["ok"], sse_result["detail"])

    # ---------- H. 审计 ----------
    from app.db.session import SessionLocal
    from app.models import OperationLog

    db = SessionLocal()
    actions = [
        a[0]
        for a in db.query(OperationLog.action)
        .filter(OperationLog.action.in_(["download_apply", "download_approve", "exit_apply", "exit_approve", "attendance_clock_in", "attendance_clock_out"]))
        .all()
    ]
    db.close()
    need = {"download_apply", "download_approve", "exit_apply", "exit_approve", "attendance_clock_in", "attendance_clock_out"}
    check("审批/打卡操作已写入审计日志", need.issubset(set(actions)), f"got={set(actions)}")

    print(f"\n===== 结果: PASS={PASS} FAIL={FAIL} =====")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
