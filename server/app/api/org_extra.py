# -*- coding: utf-8 -*-
"""组织中心扩展接口：团队共享知识库 / 下载审批 / 退出团队审批 / 企业打卡。

权限边界：
- 共享知识库：团队所有者的文档对全体成员可见可查阅；
- 下载审批：成员下载需向 owner/admin 申请，审批通过后才能下载；owner/admin 直接下载；
- 退出审批：成员退出需提交申请，owner/admin 审批通过后自动移除成员；
- 打卡：全体成员每日上下班打卡。
所有审批操作写入审计日志（services.audit.record_audit）。
"""
import json
import math
import re
import time
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.code import CONFLICT, NO_PERMISSION, NOT_FOUND, PARAM_ERROR
from app.core.deps import get_current_user, get_db
from app.core.response import BizError, ok
from app.models import (
    AttendanceFixApproval,
    AttendanceRecord,
    Document,
    DownloadApproval,
    Team,
    TeamExitApproval,
    TeamGeoConfig,
    TeamLog,
    TeamMember,
    TeamRole,
    User,
)
from app.services.audit import record_audit
from app.services.notification_service import notify_team_members, notify_user
from app.services.watermark_service import apply_watermark

router = APIRouter(prefix="/api/team", tags=["组织中心扩展"])


def _fmt(dt: datetime | None) -> str | None:
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else None


def _member_of(db: Session, team_id: int, user_id: int) -> TeamMember | None:
    return db.query(TeamMember).filter(TeamMember.team_id == team_id, TeamMember.user_id == user_id).first()


def _get_team(db: Session, team_id: int) -> Team:
    team = db.get(Team, team_id)
    if not team:
        raise BizError(NOT_FOUND, "团队不存在")
    return team


def _require_member(db: Session, team_id: int, user: User) -> TeamMember:
    me = _member_of(db, team_id, user.id)
    if not me:
        raise BizError(NO_PERMISSION, "您不是该团队成员")
    return me


def _require_manager(db: Session, team_id: int, user: User) -> TeamMember:
    me = _require_member(db, team_id, user)
    if me.role not in ("owner", "admin"):
        raise BizError(NO_PERMISSION, "仅团队所有者或管理员可操作")
    return me


def _latest_doc(db: Session, doc_id: int) -> Document | None:
    """返回共享文档系列的最新有效版本（主文档 parent_doc_id 为空）。"""
    latest = (
        db.query(Document)
        .filter(Document.parent_doc_id == doc_id, Document.is_deleted.is_(False))
        .order_by(Document.id.desc())
        .first()
    )
    if latest:
        return latest
    # P1-6 软删过滤：链上无未删版本时回退主文档，主文档已进回收站则不返回
    fallback = db.get(Document, doc_id)
    return None if (fallback and fallback.is_deleted) else fallback


def _bulk_user_map(db: Session, ids) -> dict[int, User]:
    """P1-7：一次 IN 批量取用户，替代响应构建函数内逐条 db.get(User)。"""
    clean = {i for i in ids if i}
    if not clean:
        return {}
    return {u.id: u for u in db.query(User).filter(User.id.in_(clean)).all()}


def _bulk_doc_map(db: Session, ids) -> dict[int, Document]:
    """P1-7：一次 IN 批量取文档，替代逐条 db.get(Document)。"""
    clean = {i for i in ids if i}
    if not clean:
        return {}
    return {d.id: d for d in db.query(Document).filter(Document.id.in_(clean)).all()}


def _bulk_latest_doc_map(db: Session, doc_ids) -> dict[int, Document]:
    """P1-7：一次查询取多个主文档的最新有效版本（parent_doc_id IN），语义同 _latest_doc。

    返回 {主文档id: 最新版本}；链上无未删版本的主文档不出现在结果中，由调用方回退主文档。
    """
    clean = {i for i in doc_ids if i}
    if not clean:
        return {}
    out: dict[int, Document] = {}
    rows = (
        db.query(Document)
        .filter(Document.parent_doc_id.in_(clean), Document.is_deleted.is_(False))
        .order_by(Document.parent_doc_id.asc(), Document.id.asc())
        .all()
    )
    for d in rows:
        out[d.parent_doc_id] = d  # 升序遍历，后写覆盖前值 => 保留 id 最大（最新版本）
    return out


def _owner_docs(db: Session, team: Team, page: int | None = None, page_size: int | None = None) -> tuple[int, list[Document]]:
    """团队共享知识库 = 团队所有者的文档（主文档系列，未删除）。

    P1-8：原实现一次性拉取全部主文档（无上限），现支持 page/page_size 分页并返回真实总数；
    page 为 None 时退回旧行为（返回全部，总数即长度）。
    """
    q = db.query(Document).filter(
        Document.upload_user_id == team.owner_id,
        Document.parent_doc_id.is_(None),
        Document.is_deleted.is_(False),
    )
    total = q.count() if page is not None else 0
    q = q.order_by(Document.id.desc())
    if page is not None:
        q = q.offset((page - 1) * page_size).limit(page_size)
    rows = q.all()
    return (total if page is not None else len(rows)), rows


def _shared_item(db: Session, team: Team, main_doc: Document, owner: User | None, latest: Document | None = None) -> dict:
    """共享文档条目；latest 可由批量查询预加载传入，避免逐条查版本链（P1-7）。"""
    latest = latest or _latest_doc(db, main_doc.id) or main_doc
    return {
        "id": main_doc.id,
        "doc_name": latest.doc_name,
        "origin_file_name": latest.origin_file_name,
        "file_type": latest.file_type,
        "file_size": latest.file_size,
        "version_no": latest.version_no,
        "status": latest.status,
        "summary": latest.summary,
        "update_time": _fmt(latest.update_time),
        "owner_name": owner.username if owner else None,
    }


def _download_approval_resp(
    db: Session,
    ap: DownloadApproval,
    user_map: dict[int, User] | None = None,
    doc_map: dict[int, Document] | None = None,
) -> dict:
    """下载审批响应；user_map / doc_map 可由批量查询预加载传入，避免逐条 db.get（P1-7）。"""
    if user_map is not None:
        applicant = user_map.get(ap.applicant_id)
        approver = user_map.get(ap.approver_id) if ap.approver_id else None
    else:
        applicant = db.get(User, ap.applicant_id)
        approver = db.get(User, ap.approver_id) if ap.approver_id else None
    doc = doc_map.get(ap.doc_id) if doc_map is not None else db.get(Document, ap.doc_id)
    return {
        "id": ap.id,
        "team_id": ap.team_id,
        "doc_id": ap.doc_id,
        "doc_name": doc.doc_name if doc else f"文档{ap.doc_id}",
        "origin_file_name": doc.origin_file_name if doc else "",
        "file_type": doc.file_type if doc else "",
        "applicant_id": ap.applicant_id,
        "applicant_name": applicant.username if applicant else str(ap.applicant_id),
        "approver_name": approver.username if approver else None,
        "reason": ap.reason or "",
        "status": ap.status,
        "reject_reason": ap.reject_reason,
        "apply_time": _fmt(ap.apply_time),
        "handle_time": _fmt(ap.handle_time),
    }


def _exit_approval_resp(db: Session, ap: TeamExitApproval, user_map: dict[int, User] | None = None) -> dict:
    """退出审批响应；user_map 可由批量查询预加载传入，避免逐条 db.get（P1-7）。"""
    if user_map is not None:
        applicant = user_map.get(ap.applicant_id)
        approver = user_map.get(ap.approver_id) if ap.approver_id else None
    else:
        applicant = db.get(User, ap.applicant_id)
        approver = db.get(User, ap.approver_id) if ap.approver_id else None
    return {
        "id": ap.id,
        "team_id": ap.team_id,
        "applicant_id": ap.applicant_id,
        "applicant_name": applicant.username if applicant else str(ap.applicant_id),
        "applicant_email": applicant.email if applicant else "",
        "approver_name": approver.username if approver else None,
        "reason": ap.reason or "",
        "status": ap.status,
        "reject_reason": ap.reject_reason,
        "apply_time": _fmt(ap.apply_time),
        "handle_time": _fmt(ap.handle_time),
    }


def _notify_managers(db: Session, team: Team, title: str, content: str, exclude_user_id: int | None = None) -> None:
    """通知团队所有者与管理员（审批待办）。"""
    managers = (
        db.query(TeamMember)
        .filter(TeamMember.team_id == team.id, TeamMember.role.in_(["owner", "admin"]))
        .all()
    )
    for m in managers:
        if exclude_user_id is not None and m.user_id == exclude_user_id:
            continue
        notify_user(db, m.user_id, title, content, category="approval", ntype="approval", related_id=team.id)


def _fix_approval_resp(db: Session, ap: AttendanceFixApproval, user_map: dict[int, User] | None = None) -> dict:
    """补卡审批响应；user_map 可由批量查询预加载传入，避免逐条 db.get（P1-7）。"""
    if user_map is not None:
        applicant = user_map.get(ap.user_id)
        approver = user_map.get(ap.approver_id) if ap.approver_id else None
    else:
        applicant = db.get(User, ap.user_id)
        approver = db.get(User, ap.approver_id) if ap.approver_id else None
    slot_label = SHIFT_SLOTS.get(ap.slot, {}).get("label", ap.slot)
    return {
        "id": ap.id,
        "team_id": ap.team_id,
        "user_id": ap.user_id,
        "applicant_name": applicant.username if applicant else str(ap.user_id),
        "applicant_email": applicant.email if applicant else "",
        "approver_name": approver.username if approver else None,
        "date": ap.date,
        "slot": ap.slot,
        "slot_label": slot_label,
        "reason": ap.reason or "",
        "status": ap.status,
        "reject_reason": ap.reject_reason,
        "apply_time": _fmt(ap.apply_time),
        "handle_time": _fmt(ap.handle_time),
    }


# ==================== 团队共享知识库 ====================


@router.get("/{team_id}/shared-docs")
def list_shared_docs(
    team_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """共享知识库列表：团队所有者的文档对全体成员可见。

    P1-8：原实现一次拉全部主文档，现分页（默认 50、上限 200）并返回真实 total。
    """
    team = _get_team(db, team_id)
    _require_member(db, team_id, user)
    owner = db.get(User, team.owner_id)
    total, docs = _owner_docs(db, team, page=page, page_size=page_size)
    # P1-7：原先每条文档各查一次版本链（N 次查询），改为一次 parent_doc_id IN 批量取最新版本
    latest_map = _bulk_latest_doc_map(db, [d.id for d in docs])
    items = [
        _shared_item(db, team, d, owner, latest=latest_map.get(d.id) or (d if not d.is_deleted else None))
        for d in docs
    ]
    return ok(data={"total": total, "items": items, "page": page, "page_size": page_size})


@router.get("/{team_id}/shared-docs/{doc_id}")
def shared_doc_detail(
    team_id: int, doc_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """共享文档详情（不暴露物理路径）。"""
    team = _get_team(db, team_id)
    _require_member(db, team_id, user)
    main_doc = db.get(Document, doc_id)
    if not main_doc or main_doc.upload_user_id != team.owner_id or main_doc.is_deleted or main_doc.parent_doc_id is not None:
        raise BizError(NOT_FOUND, "共享文档不存在")
    owner = db.get(User, team.owner_id)
    item = _shared_item(db, team, main_doc, owner)
    # 正文预览：从最新版本解析切片（DocChunk）按序拼接，限量返回避免撑爆响应
    latest = _latest_doc(db, main_doc.id) or main_doc
    from app.models.document import DocChunk

    chunks = (
        db.query(DocChunk)
        .filter(DocChunk.doc_id == latest.id)
        .order_by(DocChunk.chunk_index.asc(), DocChunk.id.asc())
        .all()
    )
    if chunks:
        body = "\n\n".join((c.chunk_text or "") for c in chunks)
        item["content_preview"] = body[:20000]
        item["content_pages"] = len(chunks)
    else:
        item["content_preview"] = ""
        item["content_pages"] = 0
    item["ocr_content"] = ""
    return ok(data=item)


# ==================== 下载审批 ====================


@router.post("/{team_id}/shared-docs/{doc_id}/download-request")
def request_download(
    team_id: int,
    doc_id: int,
    reason: str = Query(""),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """成员申请下载共享文档；owner/admin 直接放行（返回 status=direct）。"""
    team = _get_team(db, team_id)
    me = _require_member(db, team_id, user)
    main_doc = db.get(Document, doc_id)
    if not main_doc or main_doc.upload_user_id != team.owner_id or main_doc.is_deleted or main_doc.parent_doc_id is not None:
        raise BizError(NOT_FOUND, "共享文档不存在")
    latest = _latest_doc(db, main_doc.id) or main_doc
    if me.role in ("owner", "admin"):
        record_audit(db, user, "download_direct", "team", f"所有者/管理员直接下载共享文档《{latest.doc_name}》(doc#{doc_id})")
        return ok(data={"status": "direct", "approval_id": None}, message="您拥有直接下载权限")

    dup = (
        db.query(DownloadApproval)
        .filter(
            DownloadApproval.team_id == team_id,
            DownloadApproval.doc_id == doc_id,
            DownloadApproval.applicant_id == user.id,
            DownloadApproval.status == "pending",
        )
        .first()
    )
    if dup:
        raise BizError(CONFLICT, "您已提交过该文档的下载申请，请等待审批")
    ap = DownloadApproval(
        team_id=team_id,
        doc_id=doc_id,
        applicant_id=user.id,
        reason=(reason or "")[:255],
        status="pending",
    )
    db.add(ap)
    db.commit()
    _notify_managers(
        db,
        team,
        "新的下载审批申请",
        f"{user.username} 申请下载共享文档《{latest.doc_name}》，等待您审批",
        exclude_user_id=user.id,
    )
    db.add(
        TeamLog(
            team_id=team_id,
            user_id=user.id,
            action="download_apply",
            message=f"{user.username} 申请下载共享文档《{latest.doc_name}》",
        )
    )
    db.commit()
    record_audit(db, user, "download_apply", "team", f"提交下载申请：文档《{latest.doc_name}》(doc#{doc_id})")
    return ok(data=_download_approval_resp(db, ap), message="下载申请已提交，等待审批")


@router.get("/{team_id}/approvals/downloads")
def list_download_approvals(
    team_id: int,
    status: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """下载审批列表（仅 owner/admin，可按状态筛选 + 分页）。"""
    _get_team(db, team_id)
    _require_manager(db, team_id, user)
    q = db.query(DownloadApproval).filter(DownloadApproval.team_id == team_id)
    if status:
        q = q.filter(DownloadApproval.status == status)
    total = q.count()
    rows = q.order_by(DownloadApproval.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    # P1-7：原每条审批 3 次 db.get（文档+申请人+审批人），改为两次 IN 批量预加载
    _uid_map = _bulk_user_map(db, [a.applicant_id for a in rows] + [a.approver_id for a in rows])
    _doc_map = _bulk_doc_map(db, [a.doc_id for a in rows])
    return ok(
        data={
            "total": total,
            "items": [_download_approval_resp(db, a, user_map=_uid_map, doc_map=_doc_map) for a in rows],
        }
    )


@router.post("/{team_id}/approvals/downloads/{approval_id}/approve")
def approve_download(
    team_id: int, approval_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """审批通过下载申请：申请人获得下载权限。"""
    team = _get_team(db, team_id)
    _require_manager(db, team_id, user)
    ap = db.get(DownloadApproval, approval_id)
    if not ap or ap.team_id != team_id:
        raise BizError(NOT_FOUND, "审批记录不存在")
    if ap.status != "pending":
        raise BizError(CONFLICT, "该申请已处理")
    doc = db.get(Document, ap.doc_id)
    ap.status = "approved"
    ap.approver_id = user.id
    ap.handle_time = datetime.now()
    applicant = db.get(User, ap.applicant_id)
    db.commit()
    if applicant:
        notify_user(
            db,
            applicant.id,
            "下载审批已通过",
            f"您申请下载的《{doc.doc_name if doc else ap.doc_id}》已通过审批，可前往审批中心下载",
            category="approval",
            ntype="approval",
            related_id=team_id,
        )
        db.commit()
    record_audit(db, user, "download_approve", "team", f"通过下载申请 #{approval_id}（文档《{doc.doc_name if doc else ap.doc_id}》）")
    return ok(data=_download_approval_resp(db, ap), message="已通过下载申请")


@router.post("/{team_id}/approvals/downloads/{approval_id}/reject")
def reject_download(
    team_id: int,
    approval_id: int,
    reject_reason: str = Query(""),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """拒绝下载申请。"""
    team = _get_team(db, team_id)
    _require_manager(db, team_id, user)
    ap = db.get(DownloadApproval, approval_id)
    if not ap or ap.team_id != team_id:
        raise BizError(NOT_FOUND, "审批记录不存在")
    if ap.status != "pending":
        raise BizError(CONFLICT, "该申请已处理")
    doc = db.get(Document, ap.doc_id)
    ap.status = "rejected"
    ap.approver_id = user.id
    ap.reject_reason = (reject_reason or "未说明原因")[:255]
    ap.handle_time = datetime.now()
    applicant = db.get(User, ap.applicant_id)
    db.commit()
    if applicant:
        notify_user(
            db,
            applicant.id,
            "下载审批被拒绝",
            f"您申请下载的《{doc.doc_name if doc else ap.doc_id}》被拒绝：{ap.reject_reason}",
            category="approval",
            ntype="approval",
            related_id=team_id,
        )
        db.commit()
    record_audit(db, user, "download_reject", "team", f"拒绝下载申请 #{approval_id}：{ap.reject_reason}")
    return ok(data=_download_approval_resp(db, ap), message="已拒绝下载申请")


@router.get("/{team_id}/shared-docs/{doc_id}/download")
def download_shared_doc(
    team_id: int,
    doc_id: int,
    approval_id: int = Query(0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """下载共享文档：owner/admin 直接下载；成员需审批通过后凭 approval_id 下载。"""
    team = _get_team(db, team_id)
    me = _require_member(db, team_id, user)
    main_doc = db.get(Document, doc_id)
    if not main_doc or main_doc.upload_user_id != team.owner_id or main_doc.is_deleted or main_doc.parent_doc_id is not None:
        raise BizError(NOT_FOUND, "共享文档不存在")
    latest = _latest_doc(db, main_doc.id) or main_doc
    if not latest.file_path:
        raise BizError(NOT_FOUND, "文档文件尚未就绪，请稍后再试")
    if me.role not in ("owner", "admin"):
        ap = db.get(DownloadApproval, approval_id) if approval_id else None
        if not ap or ap.team_id != team_id or ap.doc_id != doc_id or ap.applicant_id != user.id or ap.status != "approved":
            raise BizError(NO_PERMISSION, "该文档需审批通过后才能下载")
        record_audit(db, user, "download_after_approval", "team", f"审批通过后下载共享文档《{latest.doc_name}》(doc#{doc_id})")
    # 下载水印：叠加"用户名+时间"水印防泄密溯源（水印产物不污染原始文件）
    from datetime import datetime as _dt

    ts = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
    wm_path = apply_watermark(latest.file_path, user.username, ts)
    record_audit(db, user, "download_watermarked", "team", f"下载共享文档《{latest.doc_name}》(doc#{doc_id}) 已叠加水印 [{user.username} {ts}]")
    return FileResponse(wm_path, filename=latest.origin_file_name)


# ==================== 退出团队审批 ====================


@router.post("/{team_id}/approvals/exits")
def request_exit(
    team_id: int,
    reason: str = Query(""),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """成员提交退出团队申请（owner 不可退出）。"""
    team = _get_team(db, team_id)
    me = _require_member(db, team_id, user)
    if me.role == "owner":
        raise BizError(CONFLICT, "团队所有者不能申请退出，请先移交所有权或解散团队")
    dup = (
        db.query(TeamExitApproval)
        .filter(
            TeamExitApproval.team_id == team_id,
            TeamExitApproval.applicant_id == user.id,
            TeamExitApproval.status == "pending",
        )
        .first()
    )
    if dup:
        raise BizError(CONFLICT, "您已提交过退出申请，请等待审批")
    ap = TeamExitApproval(team_id=team_id, applicant_id=user.id, reason=(reason or "")[:255], status="pending")
    db.add(ap)
    db.commit()
    _notify_managers(
        db,
        team,
        "新的退出审批申请",
        f"{user.username} 申请退出团队「{team.name}」，等待您审批",
        exclude_user_id=user.id,
    )
    db.commit()
    record_audit(db, user, "exit_apply", "team", f"提交退出团队「{team.name}」申请")
    return ok(data=_exit_approval_resp(db, ap), message="退出申请已提交，等待审批")


@router.get("/{team_id}/approvals/exits")
def list_exit_approvals(
    team_id: int,
    status: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """退出审批列表（仅 owner/admin）。"""
    _get_team(db, team_id)
    _require_manager(db, team_id, user)
    q = db.query(TeamExitApproval).filter(TeamExitApproval.team_id == team_id)
    if status:
        q = q.filter(TeamExitApproval.status == status)
    total = q.count()
    rows = q.order_by(TeamExitApproval.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    # P1-7：原每条审批 2 次 db.get（申请人+审批人），改为一次 IN 批量预加载
    _uid_map = _bulk_user_map(db, [a.applicant_id for a in rows] + [a.approver_id for a in rows])
    return ok(
        data={
            "total": total,
            "items": [_exit_approval_resp(db, a, user_map=_uid_map) for a in rows],
        }
    )


@router.post("/{team_id}/approvals/exits/{approval_id}/approve")
def approve_exit(
    team_id: int, approval_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """审批通过退出申请：自动移除成员并通知。"""
    team = _get_team(db, team_id)
    _require_manager(db, team_id, user)
    ap = db.get(TeamExitApproval, approval_id)
    if not ap or ap.team_id != team_id:
        raise BizError(NOT_FOUND, "审批记录不存在")
    if ap.status != "pending":
        raise BizError(CONFLICT, "该申请已处理")
    applicant = db.get(User, ap.applicant_id)
    tm = _member_of(db, team_id, ap.applicant_id) if applicant else None
    if tm and tm.role == "owner":
        raise BizError(CONFLICT, "团队所有者不可被移除")
    ap.status = "approved"
    ap.approver_id = user.id
    ap.handle_time = datetime.now()
    if tm:
        db.delete(tm)
    db.add(TeamLog(team_id=team_id, user_id=user.id, action="exit_approve", message=f"审批通过 {ap.applicant_id} 的退出申请，已移除成员"))
    db.commit()
    if applicant:
        notify_user(
            db,
            applicant.id,
            "退出申请已通过",
            f"您已退出团队「{team.name}」",
            category="approval",
            ntype="approval",
            related_id=team_id,
        )
        db.commit()
    record_audit(db, user, "exit_approve", "team", f"通过成员 {ap.applicant_id} 的退出申请，已移除成员")
    return ok(data=_exit_approval_resp(db, ap), message="已通过退出申请并移除成员")


@router.post("/{team_id}/approvals/exits/{approval_id}/reject")
def reject_exit(
    team_id: int,
    approval_id: int,
    reject_reason: str = Query(""),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """拒绝退出申请。"""
    team = _get_team(db, team_id)
    _require_manager(db, team_id, user)
    ap = db.get(TeamExitApproval, approval_id)
    if not ap or ap.team_id != team_id:
        raise BizError(NOT_FOUND, "审批记录不存在")
    if ap.status != "pending":
        raise BizError(CONFLICT, "该申请已处理")
    ap.status = "rejected"
    ap.approver_id = user.id
    ap.reject_reason = (reject_reason or "未说明原因")[:255]
    ap.handle_time = datetime.now()
    applicant = db.get(User, ap.applicant_id)
    db.commit()
    if applicant:
        notify_user(
            db,
            applicant.id,
            "退出申请被拒绝",
            f"您退出团队「{team.name}」的申请被拒绝：{ap.reject_reason}",
            category="approval",
            ntype="approval",
            related_id=team_id,
        )
        db.commit()
    record_audit(db, user, "exit_reject", "team", f"拒绝成员 {ap.applicant_id} 的退出申请：{ap.reject_reason}")
    return ok(data=_exit_approval_resp(db, ap), message="已拒绝退出申请")


@router.get("/{team_id}/approvals/my")
def my_approvals(team_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """我的申请记录：下载申请 + 退出申请 + 补卡申请。"""
    _get_team(db, team_id)
    _require_member(db, team_id, user)
    downloads = (
        db.query(DownloadApproval)
        .filter(DownloadApproval.team_id == team_id, DownloadApproval.applicant_id == user.id)
        .order_by(DownloadApproval.id.desc())
        .limit(50)
        .all()
    )
    exits = (
        db.query(TeamExitApproval)
        .filter(TeamExitApproval.team_id == team_id, TeamExitApproval.applicant_id == user.id)
        .order_by(TeamExitApproval.id.desc())
        .limit(50)
        .all()
    )
    fixes = (
        db.query(AttendanceFixApproval)
        .filter(AttendanceFixApproval.team_id == team_id, AttendanceFixApproval.user_id == user.id)
        .order_by(AttendanceFixApproval.id.desc())
        .limit(50)
        .all()
    )
    # P1-7：三类审批共用一个用户映射（申请人恒为当前用户），文档映射一次批量取，避免逐条 db.get
    _uid_map = _bulk_user_map(db, [user.id] + [a.approver_id for a in downloads] + [a.approver_id for a in exits] + [a.approver_id for a in fixes])
    _doc_map = _bulk_doc_map(db, [a.doc_id for a in downloads])
    return ok(
        data={
            "downloads": [_download_approval_resp(db, a, user_map=_uid_map, doc_map=_doc_map) for a in downloads],
            "exits": [_exit_approval_resp(db, a, user_map=_uid_map) for a in exits],
            "fixes": [_fix_approval_resp(db, a, user_map=_uid_map) for a in fixes],
        }
    )


@router.get("/{team_id}/approvals/pending-count")
def pending_approval_count(team_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """待审批计数（owner/admin 视角；成员返回自己的待审批申请数）。"""
    team = _get_team(db, team_id)
    me = _require_member(db, team_id, user)
    if me.role in ("owner", "admin"):
        downloads = db.query(DownloadApproval).filter(DownloadApproval.team_id == team_id, DownloadApproval.status == "pending").count()
        exits = db.query(TeamExitApproval).filter(TeamExitApproval.team_id == team_id, TeamExitApproval.status == "pending").count()
        fixes = db.query(AttendanceFixApproval).filter(AttendanceFixApproval.team_id == team_id, AttendanceFixApproval.status == "pending").count()
        return ok(data={"downloads": downloads, "exits": exits, "fixes": fixes, "total": downloads + exits + fixes})
    downloads = (
        db.query(DownloadApproval)
        .filter(DownloadApproval.team_id == team_id, DownloadApproval.applicant_id == user.id, DownloadApproval.status == "pending")
        .count()
    )
    exits = (
        db.query(TeamExitApproval)
        .filter(TeamExitApproval.team_id == team_id, TeamExitApproval.applicant_id == user.id, TeamExitApproval.status == "pending")
        .count()
    )
    fixes = (
        db.query(AttendanceFixApproval)
        .filter(AttendanceFixApproval.team_id == team_id, AttendanceFixApproval.user_id == user.id, AttendanceFixApproval.status == "pending")
        .count()
    )
    return ok(data={"downloads": downloads, "exits": exits, "fixes": fixes, "total": downloads + exits + fixes})


# ==================== 企业打卡（四段班次 + 工作区域校验） ====================

# ===== 逐行注释：企业打卡（四段班次 + 工作区域校验） =====
# 1. SHIFT_SLOTS 定义四段班次（上午上班/上午下班/下午上班/下午下班）的时间窗
#    （分钟制，服务端强校验，客户端时间不可信）；prev 字段构成打卡顺序链
#    （am_in → am_out → pm_in → pm_out），未打前一卡则后一卡会按顺序约束校验；
# 2. _haversine_m：球面距离公式计算员工定位与团队配置中心的距离（米）；
# 3. _validate_geo_clock：地理围栏强校验——团队未配置/未启用工作区域直接拒绝；
#    坐标越界拒绝；超出围栏半径拒绝（返回实际距离便于前端提示）；
# 4. _clock_rate_limit：内存滑动窗口限流，同一用户同一团队每分钟最多 5 次打卡请求，
#    防脚本刷卡；
# 5. _set_slot_time/_get_slot_time：把四段打卡时间写入/读取 AttendanceRecord
#    对应字段（am_in→clock_in_time、am_out→am_out_time、pm_in→pm_in_time、
#    pm_out→clock_out_time/pm_out_time）。
# 四段班次时间窗（分钟制，服务端强校验，客户端时间不可信）
SHIFT_SLOTS = {
    "am_in": {"label": "上午上班", "start": 0 * 60, "end": 12 * 60, "prev": None, "time": "09:00"},
    "am_out": {"label": "上午下班", "start": 8 * 60 + 30, "end": 13 * 60 + 30, "prev": "am_in", "time": "12:00"},
    "pm_in": {"label": "下午上班", "start": 12 * 60, "end": 17 * 60, "prev": "am_out", "time": "14:00"},
    "pm_out": {"label": "下午下班", "start": 13 * 60 + 30, "end": 24 * 60 - 1, "prev": "pm_in", "time": "18:30"},
}
SLOT_ORDER = ["am_in", "am_out", "pm_in", "pm_out"]

_clock_rate_bucket: dict[str, list[float]] = {}


def _today() -> str:
    return date.today().strftime("%Y-%m-%d")


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else ""


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """两点球面距离（米）。"""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _get_geo(db: Session, team_id: int) -> TeamGeoConfig | None:
    return db.query(TeamGeoConfig).filter(TeamGeoConfig.team_id == team_id).first()


def _validate_geo_clock(db: Session, team_id: int, lat: float, lng: float) -> TeamGeoConfig:
    """工作区域（地理围栏）强校验：未配置/未启用/不在围栏内均拒绝打卡。"""
    geo = _get_geo(db, team_id)
    if not geo or not geo.enabled:
        raise BizError(PARAM_ERROR, "团队尚未配置工作区域，请联系管理员在团队设置中配置后打卡")
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        raise BizError(PARAM_ERROR, "定位坐标不合法")
    dist = _haversine_m(lat, lng, geo.lat, geo.lng)
    if dist > geo.radius_m:
        raise BizError(NO_PERMISSION, f"您不在工作区域内（距离 {int(dist)}m，围栏半径 {geo.radius_m}m），禁止打卡")
    return geo


def _clock_rate_limit(team_id: int, user: User) -> None:
    """防刷：同一用户同一团队每分钟最多 5 次打卡请求。"""
    key = f"{team_id}:{user.id}"
    now = time.time()
    bucket = [t for t in _clock_rate_bucket.get(key, []) if now - t < 60]
    if len(bucket) >= 5:
        raise BizError(CONFLICT, "打卡请求过于频繁，请稍后再试")
    bucket.append(now)
    _clock_rate_bucket[key] = bucket


def _set_slot_time(rec: AttendanceRecord, slot: str, now: datetime) -> None:
    if slot == "am_in":
        rec.clock_in_time = now
    elif slot == "am_out":
        rec.am_out_time = now
    elif slot == "pm_in":
        rec.pm_in_time = now
    else:
        rec.pm_out_time = rec.clock_out_time = now


def _get_slot_time(rec: AttendanceRecord | None, slot: str) -> datetime | None:
    if not rec:
        return None
    if slot == "am_in":
        return rec.clock_in_time
    if slot == "am_out":
        return rec.am_out_time
    if slot == "pm_in":
        return rec.pm_in_time
    return rec.pm_out_time or rec.clock_out_time


@router.post("/{team_id}/attendance/clock")
def clock(
    team_id: int,
    request: Request,
    slot: str = Query(..., description="班次：am_in/am_out/pm_in/pm_out"),
    lat: float = Query(..., description="当前纬度"),
    lng: float = Query(..., description="当前经度"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """四段班次打卡：工作区域强校验 + 服务端时间 + 防重复/防篡改/限流。"""
    _get_team(db, team_id)
    _require_member(db, team_id, user)
    _clock_rate_limit(team_id, user)
    if slot not in SHIFT_SLOTS:
        raise BizError(PARAM_ERROR, "无效班次")
    geo = _validate_geo_clock(db, team_id, lat, lng)

    now = datetime.now()
    cur_min = now.hour * 60 + now.minute
    win = SHIFT_SLOTS[slot]
    if not (win["start"] <= cur_min <= win["end"]):
        raise BizError(
            PARAM_ERROR,
            f"当前时间不在「{win['label']}」打卡时段（{win['start'] // 60:02d}:{win['start'] % 60:02d}~{win['end'] // 60:02d}:{win['end'] % 60:02d}）",
        )

    today = _today()
    rec = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.team_id == team_id, AttendanceRecord.user_id == user.id, AttendanceRecord.date == today)
        .first()
    )
    if win["prev"]:
        if not rec or not _get_slot_time(rec, win["prev"]):
            raise BizError(PARAM_ERROR, f"请先完成「{SHIFT_SLOTS[win['prev']]['label']}」打卡")
    if rec and _get_slot_time(rec, slot):
        raise BizError(CONFLICT, f"今日「{win['label']}」已打卡，请勿重复打卡")
    if not rec:
        rec = AttendanceRecord(team_id=team_id, user_id=user.id, date=today)
        db.add(rec)
    _set_slot_time(rec, slot, now)

    meta = {}
    try:
        meta = json.loads(rec.checkin_meta) if rec.checkin_meta else {}
    except (ValueError, TypeError):
        meta = {}
    meta[slot] = {
        "lat": round(lat, 6),
        "lng": round(lng, 6),
        "ip": _client_ip(request),
        "ua": (request.headers.get("user-agent") or "")[:200],
        "ts": _fmt(now),
    }
    rec.checkin_meta = json.dumps(meta, ensure_ascii=False)
    db.commit()
    dist = _haversine_m(lat, lng, geo.lat, geo.lng)
    record_audit(
        db,
        user,
        f"attendance_clock_{slot}",
        "team",
        f"企业打卡：{today} {win['label']}（距围栏中心 {int(dist)}m）",
    )
    return ok(
        data={"date": today, "slot": slot, "time": _fmt(now), "distance_m": int(dist)},
        message=f"{win['label']}打卡成功",
    )


@router.get("/{team_id}/attendance/geo")
def attendance_geo(team_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """查看团队工作区域配置（成员可读）。"""
    _get_team(db, team_id)
    _require_member(db, team_id, user)
    geo = _get_geo(db, team_id)
    if not geo:
        return ok(data={"configured": False})
    return ok(
        data={
            "configured": True,
            "lat": geo.lat,
            "lng": geo.lng,
            "radius_m": geo.radius_m,
            "enabled": geo.enabled,
            "update_time": _fmt(geo.update_time),
        }
    )


@router.put("/{team_id}/attendance/geo")
def update_attendance_geo(
    team_id: int,
    lat: float = Query(...),
    lng: float = Query(...),
    radius_m: int = Query(50, ge=50, le=200000),
    enabled: bool = Query(True),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """配置团队工作区域（仅 owner/admin）。"""
    _get_team(db, team_id)
    _require_manager(db, team_id, user)
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        raise BizError(PARAM_ERROR, "经纬度不合法")
    if lat == 0 and lng == 0:
        raise BizError(PARAM_ERROR, "工作区域中心坐标无效（0,0）：请先获取定位或手动填写有效经纬度")
    geo = _get_geo(db, team_id)
    if not geo:
        geo = TeamGeoConfig(team_id=team_id)
        db.add(geo)
    geo.lat, geo.lng, geo.radius_m, geo.enabled = lat, lng, radius_m, enabled
    geo.updater_id = user.id
    db.commit()
    record_audit(db, user, "team_geo_update", "team", f"更新工作区域：中心({lat},{lng}) 半径{radius_m}m 启用={enabled}")
    return ok(
        data={"configured": True, "lat": lat, "lng": lng, "radius_m": radius_m, "enabled": enabled},
        message="工作区域已更新",
    )


@router.get("/{team_id}/attendance/today")
def attendance_today(team_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """今日打卡状态：本人四段班次 + 团队统计。"""
    _get_team(db, team_id)
    _require_member(db, team_id, user)
    today = _today()
    rec = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.team_id == team_id, AttendanceRecord.user_id == user.id, AttendanceRecord.date == today)
        .first()
    )
    now_min = datetime.now().hour * 60 + datetime.now().minute
    slots = {
        s: {
            "done": bool(rec and _get_slot_time(rec, s)),
            "time": _fmt(_get_slot_time(rec, s)) if rec else None,
            "missing": not _get_slot_time(rec, s) and now_min > SHIFT_SLOTS[s]["end"],
        }
        for s in SLOT_ORDER
    }
    status = "none"
    for s in reversed(SLOT_ORDER):
        if slots[s]["done"]:
            status = s
            break
    member_count = db.query(TeamMember).filter(TeamMember.team_id == team_id).count()
    recs = db.query(AttendanceRecord).filter(AttendanceRecord.team_id == team_id, AttendanceRecord.date == today).all()
    cnt = {s: sum(1 for r in recs if _get_slot_time(r, s)) for s in SLOT_ORDER}
    latest_times = [_get_slot_time(r, s) for r in recs for s in SLOT_ORDER if _get_slot_time(r, s)]
    latest = max(latest_times) if latest_times else None
    rate = round(cnt["am_in"] / member_count * 100, 1) if member_count else 0
    return ok(
        data={
            "date": today,
            "my": {
                "am_in_time": slots["am_in"]["time"],
                "am_out_time": slots["am_out"]["time"],
                "pm_in_time": slots["pm_in"]["time"],
                "pm_out_time": slots["pm_out"]["time"],
                "clock_in_time": slots["am_in"]["time"],
                "clock_out_time": slots["pm_out"]["time"],
                "slots": slots,
                "status": status,
            },
            "stats": {
                "member_count": member_count,
                "am_in_count": cnt["am_in"],
                "am_out_count": cnt["am_out"],
                "pm_in_count": cnt["pm_in"],
                "pm_out_count": cnt["pm_out"],
                "checked_in": cnt["am_in"],
                "checked_out": cnt["pm_out"],
                "attendance_rate": rate,
                "latest_clock": _fmt(latest),
            },
        }
    )


@router.get("/{team_id}/attendance/summary")
def attendance_summary(
    team_id: int,
    days: int = Query(7, ge=1, le=60),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """近 N 天团队出勤汇总（成员可读，供管理者日报/看板）。"""
    _get_team(db, team_id)
    _require_member(db, team_id, user)
    member_count = db.query(TeamMember).filter(TeamMember.team_id == team_id).count() or 1
    since = (date.today() - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    rows = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.team_id == team_id, AttendanceRecord.date >= since)
        .order_by(AttendanceRecord.date.asc())
        .all()
    )
    by_day: dict[str, dict] = {}
    for r in rows:
        d = by_day.setdefault(r.date, {"am_in": 0, "am_out": 0, "pm_in": 0, "pm_out": 0})
        for s in SLOT_ORDER:
            if _get_slot_time(r, s):
                d[s] += 1
    days_list = []
    for i in range(days):
        d = (date.today() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        if d > _today():
            continue
        row = by_day.get(d, {})
        am_in = row.get("am_in", 0)
        days_list.append(
            {
                "date": d,
                "am_in": am_in,
                "am_out": row.get("am_out", 0),
                "pm_in": row.get("pm_in", 0),
                "pm_out": row.get("pm_out", 0),
                "attendance_rate": round(am_in / member_count * 100, 1),
            }
        )
    return ok(data={"member_count": member_count, "days": days_list})


@router.get("/{team_id}/attendance/my")
def my_attendance(
    team_id: int,
    limit: int = Query(30, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """我的打卡记录（倒序，含四段班次时间）。"""
    _get_team(db, team_id)
    _require_member(db, team_id, user)
    items = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.team_id == team_id, AttendanceRecord.user_id == user.id)
        .order_by(AttendanceRecord.date.desc(), AttendanceRecord.id.desc())
        .limit(limit)
        .all()
    )
    now_min = datetime.now().hour * 60 + datetime.now().minute
    today = _today()
    return ok(
        data={
            "items": [
                {
                    "id": r.id,
                    "date": r.date,
                    "clock_in_time": _fmt(r.clock_in_time),
                    "clock_out_time": _fmt(r.pm_out_time or r.clock_out_time),
                    "am_in_time": _fmt(r.clock_in_time),
                    "am_out_time": _fmt(r.am_out_time),
                    "pm_in_time": _fmt(r.pm_in_time),
                    "pm_out_time": _fmt(r.pm_out_time or r.clock_out_time),
                    "missing_slots": [
                        s
                        for s in SLOT_ORDER
                        if not _get_slot_time(r, s) and (r.date < today or now_min > SHIFT_SLOTS[s]["end"])
                    ],
                }
                for r in items
            ]
        }
    )


# ==================== 考勤补卡申请（复用审批中心） ====================


@router.post("/{team_id}/attendance/fix/request")
def request_fix(
    team_id: int,
    date: str = Query(...),
    slot: str = Query(...),
    reason: str = Query("", max_length=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """提交补卡申请：迟到/漏卡时段修正，由管理员审批后写入打卡记录。"""
    team = _get_team(db, team_id)
    _require_member(db, team_id, user)
    if slot not in SHIFT_SLOTS:
        raise BizError(PARAM_ERROR, f"无效班次时段：{slot}，可选 {', '.join(SHIFT_SLOTS.keys())}")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        raise BizError(PARAM_ERROR, "日期格式须为 YYYY-MM-DD")
    if date > _today():
        raise BizError(PARAM_ERROR, "不能为未来日期申请补卡")
    # 当日尚未到达/仍在进行中的时段不允许补卡（否则会回写未来时间，污染考勤统计）
    if date == _today() and _fix_slot_time(slot, date) > datetime.now():
        raise BizError(
            PARAM_ERROR,
            f"「{SHIFT_SLOTS[slot]['label']}」时段尚未结束（基准回写时间 {SHIFT_SLOTS[slot]['time']}），请直接打卡，无需补卡",
        )
    # 该时段已有打卡记录则无需补卡
    rec_exist = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.team_id == team_id, AttendanceRecord.user_id == user.id, AttendanceRecord.date == date)
        .first()
    )
    if rec_exist and _get_slot_time(rec_exist, slot):
        raise BizError(CONFLICT, f"该日「{SHIFT_SLOTS[slot]['label']}」已有打卡记录，无需补卡")
    # 同人同团队同日期同时段去重（pending 或已通过均不允许重复申请）
    dup = (
        db.query(AttendanceFixApproval)
        .filter(
            AttendanceFixApproval.team_id == team_id,
            AttendanceFixApproval.user_id == user.id,
            AttendanceFixApproval.date == date,
            AttendanceFixApproval.slot == slot,
            AttendanceFixApproval.status.in_(["pending", "approved"]),
        )
        .first()
    )
    if dup:
        raise BizError(CONFLICT, "该日此时段已有补卡申请，请勿重复提交")
    ap = AttendanceFixApproval(
        team_id=team_id,
        user_id=user.id,
        date=date,
        slot=slot,
        reason=reason.strip() or f"补卡申请（{date} {SHIFT_SLOTS[slot]['label']}）",
        status="pending",
        apply_time=datetime.now(),
    )
    db.add(ap)
    db.flush()
    record_audit(db, user, "attendance_fix_request", "team", f"提交补卡申请（{date} {SHIFT_SLOTS[slot]['label']}），原因：{ap.reason}")
    _notify_managers(db, team, "新的考勤补卡申请", f"{user.username} 提交补卡申请（{date} {SHIFT_SLOTS[slot]['label']}），请及时审批", exclude_user_id=user.id)
    db.commit()
    return ok(data=_fix_approval_resp(db, ap))


@router.get("/{team_id}/attendance/fix/list")
def list_fixes(
    team_id: int,
    status: str = Query("", description="pending/approved/rejected，空=全部"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """补卡申请列表（管理员看全部；成员仅看自己）。

    P1-8：原实现固定 limit(100) 且无总数，改为 page/page_size 分页（默认 50、上限 200），
    返回真实 total；不传分页参数时返回第一页，保持向后兼容。
    """
    team = _get_team(db, team_id)
    me = _require_member(db, team_id, user)
    q = db.query(AttendanceFixApproval).filter(AttendanceFixApproval.team_id == team_id)
    if me.role not in ("owner", "admin"):
        q = q.filter(AttendanceFixApproval.user_id == user.id)
    if status in ("pending", "approved", "rejected"):
        q = q.filter(AttendanceFixApproval.status == status)
    total = q.count()
    items = q.order_by(AttendanceFixApproval.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    # P1-7：原每条申请 2 次 db.get（申请人+审批人），改为一次 IN 批量预加载
    _uid_map = _bulk_user_map(db, [a.user_id for a in items] + [a.approver_id for a in items])
    return ok(
        data={
            "total": total,
            "items": [_fix_approval_resp(db, a, user_map=_uid_map) for a in items],
            "page": page,
            "page_size": page_size,
        }
    )


@router.post("/{team_id}/attendance/fix/{fix_id}/approve")
def approve_fix(
    team_id: int,
    fix_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """管理员审批通过补卡申请：写入/修正该日时段打卡记录。"""
    _get_team(db, team_id)
    me = _require_member(db, team_id, user)
    if me.role not in ("owner", "admin"):
        raise BizError(NO_PERMISSION, "仅团队管理员可审批补卡申请")
    ap = db.get(AttendanceFixApproval, fix_id)
    if not ap or ap.team_id != team_id:
        raise BizError(NOT_FOUND, "补卡申请不存在")
    if ap.status != "pending":
        raise BizError(CONFLICT, "该申请已处理")
    # 防御：当日该时段基准时间仍在未来时，禁止回写未来打卡时间（避免考勤数据出现"未来打卡"）
    if ap.date == _today() and ap.slot in SHIFT_SLOTS and _fix_slot_time(ap.slot, ap.date) > datetime.now():
        raise BizError(
            PARAM_ERROR,
            f"「{SHIFT_SLOTS[ap.slot]['label']}」时段尚未结束，不能回写未来时间，请让成员直接打卡",
        )
    ap.status = "approved"
    ap.approver_id = user.id
    ap.handle_time = datetime.now()
    # 修正打卡记录：存在记录则更新对应时段，不存在则创建
    rec = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.team_id == team_id,
            AttendanceRecord.user_id == ap.user_id,
            AttendanceRecord.date == ap.date,
        )
        .first()
    )
    if not rec:
        rec = AttendanceRecord(team_id=team_id, user_id=ap.user_id, date=ap.date)
        db.add(rec)
    if ap.slot == "am_in":
        rec.clock_in_time = rec.clock_in_time or _fix_slot_time("am_in", ap.date)
        rec.am_in_time = rec.clock_in_time
    elif ap.slot == "am_out":
        rec.am_out_time = _fix_slot_time("am_out", ap.date)
    elif ap.slot == "pm_in":
        rec.pm_in_time = _fix_slot_time("pm_in", ap.date)
    elif ap.slot == "pm_out":
        rec.pm_out_time = _fix_slot_time("pm_out", ap.date)
    db.flush()
    applicant = db.get(User, ap.user_id)
    record_audit(
        db,
        user,
        "attendance_fix_approve",
        "team",
        f"审批通过补卡申请（{ap.date} {SHIFT_SLOTS[ap.slot]['label']}，申请人：{applicant.username if applicant else ap.user_id}）并修正打卡记录",
    )
    if applicant:
        notify_user(
            db,
            applicant.id,
            "补卡申请已通过",
            f"您的补卡申请（{ap.date} {SHIFT_SLOTS[ap.slot]['label']}）已审批通过，打卡记录已修正",
            category="approval",
            ntype="approval",
            related_id=team_id,
        )
    db.commit()
    return ok(data=_fix_approval_resp(db, ap))


@router.post("/{team_id}/attendance/fix/{fix_id}/reject")
def reject_fix(
    team_id: int,
    fix_id: int,
    reject_reason: str = Query("", max_length=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """管理员驳回补卡申请。"""
    _get_team(db, team_id)
    me = _require_member(db, team_id, user)
    if me.role not in ("owner", "admin"):
        raise BizError(NO_PERMISSION, "仅团队管理员可审批补卡申请")
    ap = db.get(AttendanceFixApproval, fix_id)
    if not ap or ap.team_id != team_id:
        raise BizError(NOT_FOUND, "补卡申请不存在")
    if ap.status != "pending":
        raise BizError(CONFLICT, "该申请已处理")
    ap.status = "rejected"
    ap.approver_id = user.id
    ap.handle_time = datetime.now()
    ap.reject_reason = reject_reason.strip() or "管理员驳回"
    db.flush()
    applicant = db.get(User, ap.user_id)
    record_audit(
        db,
        user,
        "attendance_fix_reject",
        "team",
        f"驳回补卡申请（{ap.date} {SHIFT_SLOTS[ap.slot]['label']}，申请人：{applicant.username if applicant else ap.user_id}）",
    )
    if applicant:
        notify_user(
            db,
            applicant.id,
            "补卡申请被驳回",
            f"您的补卡申请（{ap.date} {SHIFT_SLOTS[ap.slot]['label']}）未通过审批" + (f"：{ap.reject_reason}" if ap.reject_reason else ""),
            category="approval",
            ntype="approval",
            related_id=team_id,
        )
    db.commit()
    return ok(data=_fix_approval_resp(db, ap))


def _fix_slot_time(slot: str, date: str | None = None):
    """审批通过后按班次基准时间生成补卡打卡时间（分钟精度）。

    date 为补卡申请日期（YYYY-MM-DD），缺省用当天；避免历史日期补卡回写时落到错误日期。
    """
    spec = SHIFT_SLOTS.get(slot, {})
    hm = spec.get("time", "09:00").split(":")
    if date:
        base = datetime.strptime(date, "%Y-%m-%d")
    else:
        base = datetime.now()
    return base.replace(hour=int(hm[0]), minute=int(hm[1]), second=0, microsecond=0)


# ============================================================
# 自定义角色与权限矩阵（组织中心）
# ============================================================

# 权限点目录：key -> 展示名。所有自定义角色权限矩阵基于此勾选。
PERM_CATALOG: list[dict] = [
    {"key": "manage_team", "label": "编辑团队信息"},
    {"key": "invite_members", "label": "邀请成员"},
    {"key": "manage_members", "label": "调整成员角色 / 移除成员"},
    {"key": "send_notice", "label": "发送团队通知"},
    {"key": "manage_docs", "label": "管理共享文档"},
    {"key": "approve_download", "label": "审批下载申请"},
    {"key": "approve_exit", "label": "审批退出申请"},
    {"key": "approve_fix", "label": "审批补卡申请"},
    {"key": "manage_geo", "label": "配置考勤围栏"},
    {"key": "view_audit", "label": "查看审计日志"},
    {"key": "manage_roles", "label": "管理自定义角色"},
]

# 内置角色默认权限矩阵（owner/admin/member 只读展示，不可编辑）
BUILTIN_ROLE_PERMS: dict[str, list[str]] = {
    "owner": [p["key"] for p in PERM_CATALOG],
    "admin": [p["key"] for p in PERM_CATALOG if p["key"] != "manage_roles"],
    "member": [],
}


def _require_owner(db: Session, team_id: int, user: User) -> TeamMember:
    """仅团队所有者可操作角色管理。"""
    me = _require_member(db, team_id, user)
    if me.role != "owner":
        raise BizError(NO_PERMISSION, "仅团队所有者可管理角色")
    return me


def _perm_allowed(db: Session, team_id: int, user: User, perm: str) -> bool:
    """权限点判定：owner 全量；admin 按内置矩阵；自定义角色按其配置的权限点。"""
    me = _member_of(db, team_id, user.id)
    if not me:
        return False
    if me.role == "owner":
        return True
    if me.role == "admin":
        return perm in BUILTIN_ROLE_PERMS["admin"]
    if me.role in ("member", ""):
        return False
    # 自定义角色：查角色权限配置
    role = db.query(TeamRole).filter(TeamRole.role_key == me.role, TeamRole.team_id == team_id).first()
    if not role:
        return False
    return perm in (role.perms or [])


def _role_resp(r: TeamRole) -> dict:
    return {
        "id": r.id,
        "team_id": r.team_id,
        "role_key": r.role_key,
        "role_name": r.role_name,
        "perms": r.perms or [],
        "built_in": r.built_in,
        "remark": r.remark,
        "member_count": 0,
        "create_time": _fmt(r.create_time),
    }


@router.get("/{team_id}/roles")
def list_roles(team_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """角色列表：内置三档（只读）+ 自定义角色（可编辑），并统计各角色成员数。"""
    _require_member(db, team_id, user)
    builtins = [
        {"id": None, "team_id": team_id, "role_key": "owner", "role_name": "所有者", "perms": BUILTIN_ROLE_PERMS["owner"], "built_in": True, "remark": "团队最高权限，不可编辑", "member_count": 0, "create_time": None},
        {"id": None, "team_id": team_id, "role_key": "admin", "role_name": "管理员", "perms": BUILTIN_ROLE_PERMS["admin"], "built_in": True, "remark": "默认管理权限，不可编辑", "member_count": 0, "create_time": None},
        {"id": None, "team_id": team_id, "role_key": "member", "role_name": "成员", "perms": BUILTIN_ROLE_PERMS["member"], "built_in": True, "remark": "基础协作权限，不可编辑", "member_count": 0, "create_time": None},
    ]
    customs = db.query(TeamRole).filter(TeamRole.team_id == team_id).order_by(TeamRole.id.asc()).all()
    # P1-7：原实现把该团队全部成员行拉到内存里累加，改为数据库 GROUP BY 聚合
    count_map = dict(
        db.query(TeamMember.role, func.count(TeamMember.id))
        .filter(TeamMember.team_id == team_id)
        .group_by(TeamMember.role)
        .all()
    )
    for b in builtins:
        b["member_count"] = count_map.get(b["role_key"], 0)
    items = builtins + [_role_resp(r) for r in customs]
    for it in items:
        if it["role_key"] in count_map:
            it["member_count"] = count_map[it["role_key"]]
    return ok(data={"catalog": PERM_CATALOG, "roles": items})


@router.post("/{team_id}/roles")
def create_role(
    team_id: int,
    payload: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建自定义角色：role_name + perms 权限点数组。"""
    _require_owner(db, team_id, user)
    name = (payload.get("role_name") or "").strip()
    perms = payload.get("perms") or []
    remark = (payload.get("remark") or "").strip()
    if not name or len(name) > 64:
        raise BizError(PARAM_ERROR, "角色名称必填且不超过 64 字")
    if not isinstance(perms, list):
        raise BizError(PARAM_ERROR, "perms 必须为权限点数组")
    valid_keys = {p["key"] for p in PERM_CATALOG}
    bad = [p for p in perms if p not in valid_keys]
    if bad:
        raise BizError(PARAM_ERROR, f"非法权限点：{', '.join(str(x) for x in bad)}")
    perms = list(dict.fromkeys(perms))
    if db.query(TeamRole).filter(TeamRole.team_id == team_id, TeamRole.role_name == name).first():
        raise BizError(PARAM_ERROR, f"角色「{name}」已存在")
    role = TeamRole(team_id=team_id, role_key="", role_name=name, perms=perms, built_in=False, remark=remark)
    db.add(role)
    db.flush()
    role.role_key = f"custom_{role.id}"
    db.commit()
    db.refresh(role)
    record_audit(db, user, "role_create", "team", f"创建自定义角色「{name}」（权限 {len(perms)} 项）")
    return ok(data=_role_resp(role), message=f"角色「{name}」已创建")


@router.put("/{team_id}/roles/{role_id}")
def update_role(
    team_id: int,
    role_id: int,
    payload: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新自定义角色：重命名 / 调整权限矩阵。"""
    _require_owner(db, team_id, user)
    role = db.get(TeamRole, role_id)
    if not role or role.team_id != team_id or role.built_in:
        raise BizError(NOT_FOUND, "角色不存在或为内置角色")
    name = (payload.get("role_name") or "").strip()
    perms = payload.get("perms")
    remark = payload.get("remark")
    if name:
        if len(name) > 64:
            raise BizError(PARAM_ERROR, "角色名称不超过 64 字")
        dup = db.query(TeamRole).filter(TeamRole.team_id == team_id, TeamRole.role_name == name, TeamRole.id != role.id).first()
        if dup:
            raise BizError(PARAM_ERROR, f"角色「{name}」已存在")
        role.role_name = name
    if perms is not None:
        if not isinstance(perms, list):
            raise BizError(PARAM_ERROR, "perms 必须为权限点数组")
        valid_keys = {p["key"] for p in PERM_CATALOG}
        bad = [p for p in perms if p not in valid_keys]
        if bad:
            raise BizError(PARAM_ERROR, f"非法权限点：{', '.join(str(x) for x in bad)}")
        role.perms = list(dict.fromkeys(perms))
    if remark is not None:
        role.remark = str(remark).strip()
    db.commit()
    db.refresh(role)
    record_audit(db, user, "role_update", "team", f"更新自定义角色「{role.role_name}」权限矩阵")
    return ok(data=_role_resp(role), message="角色已更新")


@router.delete("/{team_id}/roles/{role_id}")
def delete_role(
    team_id: int,
    role_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除自定义角色：引用该角色的成员自动降级为普通成员。"""
    _require_owner(db, team_id, user)
    role = db.get(TeamRole, role_id)
    if not role or role.team_id != team_id or role.built_in:
        raise BizError(NOT_FOUND, "角色不存在或为内置角色")
    affected = db.query(TeamMember).filter(TeamMember.team_id == team_id, TeamMember.role == role.role_key).all()
    for tm in affected:
        tm.role = "member"
    db.delete(role)
    db.commit()
    record_audit(db, user, "role_delete", "team", f"删除自定义角色「{role.role_name}」（{len(affected)} 名成员降级为成员）")
    return ok(data={"role_id": role_id, "downgraded": len(affected)}, message=f"角色「{role.role_name}」已删除")


@router.get("/{team_id}/roles/{role_key}/members")
def role_members(team_id: int, role_key: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """按角色查看成员（owner/admin 可用）。"""
    _require_member(db, team_id, user)
    me = _member_of(db, team_id, user.id)
    if me.role not in ("owner", "admin") and not _perm_allowed(db, team_id, user, "manage_members"):
        raise BizError(NO_PERMISSION, "无权限查看角色成员")
    rows = db.query(TeamMember).filter(TeamMember.team_id == team_id, TeamMember.role == role_key).all()
    # P1-7：原实现按成员逐条 db.get(User)（N+1），改为一次 IN 批量取
    user_ids = {tm.user_id for tm in rows if tm.user_id is not None}
    user_map = (
        {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}
    )
    data = []
    for tm in rows:
        u = user_map.get(tm.user_id)
        data.append({"user_id": tm.user_id, "username": u.username if u else f"#{tm.user_id}", "email": u.email if u else "", "joined_at": _fmt(tm.joined_at)})
    return ok(data={"role_key": role_key, "members": data})
