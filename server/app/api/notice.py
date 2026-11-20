# -*- coding: utf-8 -*-
"""通知中心：分类（团队动态/审批消息/系统消息）+ 未读已读 + 分页 + SSE 实时推送。

- 团队动态(team)：团队通知、成员变动等；
- 审批消息(approval)：下载审批、退出审批等业务审批；
- 系统消息(system)：Agent 任务完成、系统公告等。
"""
import asyncio
import json
import time

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.code import NO_PERMISSION, NOT_FOUND, PARAM_ERROR
from app.core.deps import get_current_user, get_db
from app.core.response import BizError, ok
from app.core.security import decode_token
from app.db.session import SessionLocal
from app.models import Team, TeamLog, TeamMember, TeamNotice, TeamNoticeRead, User, UserNotification
from app.schemas.notice import NoticeResp, SendNoticeReq
from app.services.notification_service import notify_team_members

router = APIRouter(prefix="/api/notice", tags=["通知中心"])


def _fmt(dt) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else ""


def _member_of(db: Session, team_id: int, user_id: int) -> TeamMember | None:
    return db.query(TeamMember).filter(TeamMember.team_id == team_id, TeamMember.user_id == user_id).first()


def _notice_resp(db: Session, notice: TeamNotice, user: User) -> NoticeResp:
    team = db.get(Team, notice.team_id)
    sender = db.get(User, notice.sender_id)
    direction = "sent" if notice.sender_id == user.id else "received"
    read = None
    if direction == "received":
        read = (
            db.query(TeamNoticeRead)
            .filter(TeamNoticeRead.notice_id == notice.id, TeamNoticeRead.user_id == user.id)
            .first()
            is not None
        )
    return NoticeResp(
        id=notice.id,
        team_id=notice.team_id,
        team_name=team.name if team else f"团队{notice.team_id}",
        sender_id=notice.sender_id,
        sender_name=sender.username if sender else str(notice.sender_id),
        title=notice.title,
        content=notice.content,
        create_time=_fmt(notice.create_time),
        direction=direction,
        read=read,
    )


@router.post("/send")
def send_notice(req: SendNoticeReq, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """发送团队通知（仅 owner/admin）：同步写入成员个人通知（团队动态）。"""
    team = db.get(Team, req.team_id)
    if not team:
        raise BizError(NOT_FOUND, "团队不存在")
    me = _member_of(db, team.id, user.id)
    if not me or me.role not in ("owner", "admin"):
        raise BizError(NO_PERMISSION, "仅团队所有者或管理员可发送通知")
    notice = TeamNotice(team_id=team.id, sender_id=user.id, title=req.title.strip(), content=req.content.strip())
    db.add(notice)
    db.add(
        TeamLog(
            team_id=team.id,
            user_id=user.id,
            action="notice_send",
            message=f"发送团队通知《{notice.title}》",
        )
    )
    notify_team_members(
        db,
        team.id,
        notice.title,
        notice.content,
        category="team",
        ntype="team",
        exclude_user_id=user.id,
        related_id=team.id,
    )
    db.commit()
    return ok(data=_notice_resp(db, notice, user).model_dump(mode="json"), message="通知已发送")


@router.get("/list")
def list_notices(
    category: str = Query("", description="team/approval/system，空=全部"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """我的通知列表（个人通知中心）：分类过滤 + 分页，按时间倒序。"""
    base = db.query(UserNotification).filter(UserNotification.user_id == user.id)
    if category:
        base = base.filter(UserNotification.category == category)
    total = base.count()
    rows = base.order_by(UserNotification.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    counts = {
        "team": db.query(UserNotification).filter(UserNotification.user_id == user.id, UserNotification.category == "team").count(),
        "approval": db.query(UserNotification).filter(UserNotification.user_id == user.id, UserNotification.category == "approval").count(),
        "system": db.query(UserNotification).filter(UserNotification.user_id == user.id, UserNotification.category == "system").count(),
    }
    items = [
        {
            "id": n.id,
            "title": n.title,
            "content": n.content,
            "ntype": n.ntype,
            "category": n.category,
            "related_id": n.related_id,
            "read": n.read,
            "create_time": _fmt(n.create_time),
        }
        for n in rows
    ]
    return ok(data={"total": total, "items": items, "category_counts": counts})


@router.get("/unread-count")
def unread_count(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """未读通知数：总数 + 分类未读数。"""
    base = db.query(UserNotification).filter(UserNotification.user_id == user.id, UserNotification.read.is_(False))
    count = base.count()
    team = (
        db.query(UserNotification)
        .filter(UserNotification.user_id == user.id, UserNotification.read.is_(False), UserNotification.category == "team")
        .count()
    )
    approval = (
        db.query(UserNotification)
        .filter(UserNotification.user_id == user.id, UserNotification.read.is_(False), UserNotification.category == "approval")
        .count()
    )
    system = (
        db.query(UserNotification)
        .filter(UserNotification.user_id == user.id, UserNotification.read.is_(False), UserNotification.category == "system")
        .count()
    )
    return ok(data={"count": count, "team": team, "approval": approval, "system": system})


@router.post("/{notification_id}/read")
def mark_notice_read(notification_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """标记单条通知已读（幂等）。"""
    n = db.query(UserNotification).filter(UserNotification.id == notification_id, UserNotification.user_id == user.id).first()
    if not n:
        raise BizError(NOT_FOUND, "通知不存在")
    n.read = True
    db.commit()
    return ok(data={"id": n.id, "read": True}, message="已标记为已读")


@router.post("/read-all")
def mark_all_read(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """一键全部已读。"""
    db.query(UserNotification).filter(UserNotification.user_id == user.id, UserNotification.read.is_(False)).update(
        {"read": True}
    )
    db.commit()
    return ok(message="已全部标记为已读")


@router.get("/events")
async def notice_events(
    request: Request,
    token: str = Query(""),
    authorization: str = Header(""),
    once: bool = Query(False, description="true 时仅返回当前未读快照（非流式，毫秒级返回）"),
    max_seconds: int = Query(60, ge=1, le=600, description="SSE 单连接最长存活秒数，到时自动结束"),
    interval: int = Query(5, ge=1, le=60, description="服务端轮询间隔秒"),
    db: Session = Depends(get_db),
):
    """通知实时推送（SSE）：未读数变化时下发事件，前端据此刷新角标与列表。

    非阻塞设计（防止拖垮 uvicorn 事件循环）：
    1. 所有同步 SQLAlchemy 查询均通过 asyncio.to_thread 丢到线程池执行，绝不在事件循环内做阻塞 IO；
    2. 首帧立即下发（不等待首个轮询周期），避免客户端空等被误判为 hang；
    3. 连接有最长存活时间 max_seconds，到点主动发 end 事件并关闭，杜绝连接泄漏；
    4. 每个周期检测客户端断开，断开发起方立即退出循环；
    5. 支持 once=true 直接返回 JSON 快照，供健康检查/探活/前端首次渲染同步获取。
    """
    cred = ""
    if authorization.lower().startswith("bearer "):
        cred = authorization[7:]
    elif token:
        cred = token
    payload = decode_token(cred)
    if not payload or payload.get("type") != "access":
        from app.core.code import NOT_AUTH

        raise BizError(NOT_AUTH, "未登录或 token 无效", status_code=401)
    user_id = int(payload["sub"])
    user = db.get(User, user_id)
    if not user or user.status != "active":
        from app.core.code import NOT_AUTH

        raise BizError(NOT_AUTH, "用户不存在或已禁用", status_code=401)

    def _snapshot() -> dict:
        """线程池内执行：独立会话查询，查询完立即释放连接。"""
        s = SessionLocal()
        try:
            unread = (
                s.query(UserNotification)
                .filter(UserNotification.user_id == user_id, UserNotification.read.is_(False))
                .count()
            )
            last = (
                s.query(UserNotification)
                .filter(UserNotification.user_id == user_id)
                .order_by(UserNotification.id.desc())
                .first()
            )
            return {
                "type": "notice",
                "unread": unread,
                "latest_id": last.id if last else None,
                "latest_title": last.title if last else None,
                "latest_category": last.category if last else None,
                "ts": int(time.time()),
            }
        finally:
            s.close()

    snapshot = await asyncio.to_thread(_snapshot)

    if once:
        return ok(data=snapshot)

    def _sig(data: dict) -> str:
        return f"{data['unread']}:{data['latest_id'] or 0}"

    async def event_stream():
        last_sig = _sig(snapshot)
        yield ": connected\n\n"
        yield f"data: {json.dumps(snapshot, ensure_ascii=False)}\n\n"
        started = time.monotonic()
        while True:
            if await request.is_disconnected():
                return
            if time.monotonic() - started >= max_seconds:
                yield 'event: end\ndata: {"reason": "timeout"}\n\n'
                return
            await asyncio.sleep(interval)
            if await request.is_disconnected():
                return
            try:
                data = await asyncio.to_thread(_snapshot)
            except Exception:
                # 单次查询失败不中断连接
                yield ": heartbeat\n\n"
                continue
            sig = _sig(data)
            if sig != last_sig:
                last_sig = sig
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            else:
                yield ": heartbeat\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ---------- 兼容接口（全局通知 / 团队通知旧语义保留） ----------


@router.get("/global/list")
def global_notice_list(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
):
    """全局通知列表：Agent 任务完成、系统消息、团队动态等个人通知。"""
    rows = (
        db.query(UserNotification)
        .filter(UserNotification.user_id == user.id)
        .order_by(UserNotification.id.desc())
        .offset(max(offset, 0))
        .limit(min(max(limit, 1), 100))
        .all()
    )
    data = [
        {
            "id": n.id,
            "title": n.title,
            "content": n.content,
            "ntype": n.ntype,
            "category": n.category,
            "related_id": n.related_id,
            "read": n.read,
            "create_time": _fmt(n.create_time),
        }
        for n in rows
    ]
    return ok(data=data)


@router.get("/global/unread-count")
def global_unread_count(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    count = db.query(UserNotification).filter(UserNotification.user_id == user.id, UserNotification.read.is_(False)).count()
    return ok(data={"count": count})


@router.post("/global/read/{notification_id}")
def global_mark_read(notification_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.query(UserNotification).filter(UserNotification.id == notification_id, UserNotification.user_id == user.id).first()
    if not n:
        raise BizError(NOT_FOUND, "通知不存在")
    n.read = True
    db.commit()
    return ok(data={"id": n.id, "read": True}, message="已标记为已读")


@router.post("/global/read-all")
def global_mark_read_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(UserNotification).filter(UserNotification.user_id == user.id, UserNotification.read.is_(False)).update(
        {"read": True}
    )
    db.commit()
    return ok(message="已全部标记为已读")


@router.post("/team-notice/{notice_id}/read")
def mark_team_notice_read(notice_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """标记团队通知已读（TeamNotice 旧语义，幂等）。"""
    notice = db.get(TeamNotice, notice_id)
    if not notice:
        raise BizError(NOT_FOUND, "通知不存在")
    me = _member_of(db, notice.team_id, user.id)
    if not me:
        raise BizError(NO_PERMISSION, "您不是该团队成员，无法查看该通知")
    if notice.sender_id == user.id:
        raise BizError(PARAM_ERROR, "本人发送的通知不计入已读")
    existing = (
        db.query(TeamNoticeRead)
        .filter(TeamNoticeRead.notice_id == notice.id, TeamNoticeRead.user_id == user.id)
        .first()
    )
    if not existing:
        db.add(TeamNoticeRead(notice_id=notice.id, user_id=user.id))
        db.commit()
    return ok(data={"notice_id": notice.id, "read": True}, message="已标记为已读")
