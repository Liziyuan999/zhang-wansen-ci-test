# -*- coding: utf-8 -*-
"""管理员后台：用户管理、部门管理、配置、审计日志、LLM 调用记录。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.code import CONFLICT, NOT_FOUND
from app.core.deps import get_db, require_admin
from app.core.response import BizError, ok
from app.models import Conversation, ConversationMsg, Department, Document, Feedback, LlmCallLog, OperationLog, SysConfig, Team, TeamMember, TeamRole, User
from app.schemas.admin import AdminUserUpdateReq, ConfigUpdateReq, DeptCreateReq, DeptUpdateReq

router = APIRouter(prefix="/api/admin", tags=["管理员"])


# ---------- P1-7：批量映射工具（避免逐条查库 / 全表加载） ----------
def _user_name_map(db: Session, user_ids) -> dict[int, str]:
    """按 id 集合一次性 IN 查询用户名，替代 db.query(User).all() 全表加载与循环 db.get。"""
    ids = {i for i in user_ids if i is not None}
    if not ids:
        return {}
    return {uid: uname for uid, uname in db.query(User.id, User.username).filter(User.id.in_(ids)).all()}


def _dept_name_map(db: Session, dept_ids) -> dict[int, str]:
    """按 id 集合一次性 IN 查询部门名，替代全表加载。"""
    ids = {i for i in dept_ids if i is not None}
    if not ids:
        return {}
    return {did: dname for did, dname in db.query(Department.id, Department.dept_name).filter(Department.id.in_(ids)).all()}


# ---------- 用户管理 ----------
@router.get("/users")
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    keyword: str = Query(""),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    q = db.query(User)
    if keyword:
        q = q.filter(User.username.contains(keyword) | User.email.contains(keyword))
    total = q.count()
    users = q.order_by(User.create_time.desc(), User.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    dept_map = _dept_name_map(db, [u.dept_id for u in users])
    items = [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "role": u.role,
            "status": u.status,
            "dept_id": u.dept_id,
            "dept_name": dept_map.get(u.dept_id),
            "last_login_time": u.last_login_time,
            "create_time": u.create_time,
        }
        for u in users
    ]
    return ok(data={"total": total, "items": items})


@router.patch("/users/{user_id}")
def update_user(user_id: int, req: AdminUserUpdateReq, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if not user:
        raise BizError(NOT_FOUND, "用户不存在")
    if req.role is not None:
        user.role = req.role
    if req.status is not None:
        user.status = req.status
    if req.dept_id is not None:
        if not db.get(Department, req.dept_id):
            raise BizError(NOT_FOUND, "部门不存在")
        user.dept_id = req.dept_id
    if req.username is not None:
        user.username = req.username
    db.commit()
    return ok(message="用户已更新")


@router.post("/users/{user_id}/unlock")
def unlock_user(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """管理员强制解锁：解除登录锁定并复位失败计数（敏感操作写审计）。"""
    user = db.get(User, user_id)
    if not user:
        raise BizError(NOT_FOUND, "用户不存在")
    from app.services.login_security import unlock_user as _unlock

    _unlock(db, user, operator=admin, via="admin")
    return ok(message=f"用户 {user.email} 已解锁")


# ---------- 部门管理 ----------
def _dept_tree(db: Session) -> list[dict]:
    """构造部门树（含成员数、负责人名称）。"""
    rows = db.query(Department).order_by(Department.sort_order.asc(), Department.id.asc()).all()
    member_counts = dict(db.query(User.dept_id, func.count(User.id)).group_by(User.dept_id).all())
    leader_ids = {d.leader_id for d in rows if d.leader_id is not None}
    leader_map = {}
    if leader_ids:
        for u in db.query(User).filter(User.id.in_(leader_ids)).all():
            leader_map[u.id] = u.username
    by_parent: dict[int | None, list[Department]] = {}
    for d in rows:
        by_parent.setdefault(d.parent_id, []).append(d)

    def build(pid: int | None) -> list[dict]:
        nodes = []
        for d in by_parent.get(pid, []):
            nodes.append(
                {
                    "id": d.id,
                    "dept_name": d.dept_name,
                    "parent_id": d.parent_id,
                    "leader_id": d.leader_id,
                    "leader_name": leader_map.get(d.leader_id) if d.leader_id is not None else None,
                    "description": d.description,
                    "sort_order": d.sort_order,
                    "member_count": member_counts.get(d.id, 0),
                    "create_time": d.create_time,
                    "children": build(d.id),
                }
            )
        return nodes

    return build(None)


def _dept_ancestors(db: Session, dept: Department) -> set[int]:
    """返回 dept 的全部祖先 id（沿 parent_id 向上），用于环校验。"""
    seen: set[int] = set()
    cur = dept.parent_id
    while cur is not None and cur not in seen:
        seen.add(cur)
        parent = db.get(Department, cur)
        if not parent:
            break
        cur = parent.parent_id
    return seen


def _check_dept_sibling_name(db: Session, dept_name: str, parent_id: int | None, exclude_id: int | None = None) -> bool:
    """同级（相同 parent_id，含顶级 None）是否已存在同名部门。"""
    q = db.query(Department).filter(Department.dept_name == dept_name)
    if parent_id is None:
        q = q.filter(Department.parent_id.is_(None))
    else:
        q = q.filter(Department.parent_id == parent_id)
    if exclude_id is not None:
        q = q.filter(Department.id != exclude_id)
    return q.first() is not None


@router.get("/departments")
def list_depts(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return ok(data=_dept_tree(db))


@router.post("/departments")
def create_dept(req: DeptCreateReq, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    name = req.dept_name.strip()
    if not name:
        raise BizError(CONFLICT, "部门名称不能为空")
    if req.parent_id is not None and not db.get(Department, req.parent_id):
        raise BizError(NOT_FOUND, "上级部门不存在")
    if req.leader_id is not None and not db.get(User, req.leader_id):
        raise BizError(NOT_FOUND, "负责人不存在")
    if _check_dept_sibling_name(db, name, req.parent_id):
        raise BizError(CONFLICT, "同级已存在同名部门")
    dept = Department(
        dept_name=name,
        parent_id=req.parent_id,
        leader_id=req.leader_id,
        description=req.description,
        sort_order=req.sort_order,
    )
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return ok(data={"id": dept.id, "dept_name": dept.dept_name}, message="部门已创建")


@router.put("/departments/{dept_id}")
def update_dept(dept_id: int, req: DeptUpdateReq, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    dept = db.get(Department, dept_id)
    if not dept:
        raise BizError(NOT_FOUND, "部门不存在")
    fields = req.model_fields_set
    if "dept_name" in fields:
        name = (req.dept_name or "").strip()
        if not name:
            raise BizError(CONFLICT, "部门名称不能为空")
        if _check_dept_sibling_name(db, name, dept.parent_id, exclude_id=dept.id):
            raise BizError(CONFLICT, "同级已存在同名部门")
        dept.dept_name = name
    if "parent_id" in fields:
        new_parent = req.parent_id
        if new_parent is not None:
            if new_parent == dept.id:
                raise BizError(CONFLICT, "上级部门不能是自身")
            parent = db.get(Department, new_parent)
            if not parent:
                raise BizError(NOT_FOUND, "上级部门不存在")
            if dept.id in _dept_ancestors(db, parent):
                raise BizError(CONFLICT, "上级部门不能是自身的下级部门（会形成环）")
        if _check_dept_sibling_name(db, dept.dept_name, new_parent, exclude_id=dept.id):
            raise BizError(CONFLICT, "同级已存在同名部门")
        dept.parent_id = new_parent
    if "leader_id" in fields:
        if req.leader_id is not None and not db.get(User, req.leader_id):
            raise BizError(NOT_FOUND, "负责人不存在")
        dept.leader_id = req.leader_id
    if "description" in fields:
        dept.description = req.description
    if "sort_order" in fields:
        dept.sort_order = req.sort_order or 0
    db.commit()
    return ok(message="部门已更新")


@router.delete("/departments/{dept_id}")
def delete_dept(dept_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    dept = db.get(Department, dept_id)
    if not dept:
        raise BizError(NOT_FOUND, "部门不存在")
    child = db.query(Department).filter(Department.parent_id == dept_id).first()
    if child:
        raise BizError(CONFLICT, "该部门存在下级部门，无法删除")
    member = db.query(User).filter(User.dept_id == dept_id).first()
    if member:
        raise BizError(CONFLICT, "该部门仍有成员，无法删除")
    db.delete(dept)
    db.commit()
    return ok(message="部门已删除")


# ---------- 审计日志 ----------
@router.get("/logs")
def list_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    action: str = Query(""),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    q = db.query(OperationLog)
    if action:
        q = q.filter(OperationLog.action == action)
    total = q.count()
    logs = (
        q.order_by(OperationLog.create_time.desc(), OperationLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        {
            "id": l.id,
            "user_id": l.user_id,
            "username": l.username,
            "dept_id": l.dept_id,
            "action": l.action,
            "module": l.module,
            "method": l.method,
            "path": l.path,
            "detail": l.detail,
            "ip": l.ip,
            "status": l.status,
            "duration_ms": l.duration_ms,
            "create_time": l.create_time,
        }
        for l in logs
    ]
    return ok(data={"total": total, "items": items})


# ---------- LLM 调用记录 ----------
@router.get("/llm-logs")
def list_llm_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    q = db.query(LlmCallLog)
    total = q.count()
    logs = q.order_by(LlmCallLog.create_time.desc(), LlmCallLog.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = [
        {
            "id": l.id,
            "user_id": l.user_id,
            "scenario": l.scenario,
            "model_name": l.model_name,
            "prompt_tokens": l.prompt_tokens,
            "completion_tokens": l.completion_tokens,
            "total_tokens": l.total_tokens,
            "latency_ms": l.latency_ms,
            "is_success": l.is_success,
            "error_msg": l.error_msg,
            "create_time": l.create_time,
        }
        for l in logs
    ]
    return ok(data={"total": total, "items": items})


# ---------- 系统配置 ----------
@router.get("/configs")
def list_configs(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    rows = db.query(SysConfig).order_by(SysConfig.id.asc()).all()
    return ok(data=[{"config_key": c.config_key, "config_value": c.config_value, "description": c.description} for c in rows])


@router.put("/configs/{config_key}")
def update_config(config_key: str, req: ConfigUpdateReq, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    if config_key != req.config_key:
        raise BizError(CONFLICT, "路径与请求体配置键不一致")
    row = db.query(SysConfig).filter(SysConfig.config_key == req.config_key).first()
    if not row:
        row = SysConfig(config_key=req.config_key)
        db.add(row)
    row.config_value = req.config_value
    row.description = req.description
    db.commit()
    return ok(message="配置已保存")


# ---------- 文档总览 ----------
@router.get("/documents")
def admin_list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    keyword: str = "",
    file_type: str = "",
    status: str = "",
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    q = db.query(Document).filter(Document.is_deleted.is_(False))
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(db.or_(Document.doc_name.like(like), Document.origin_file_name.like(like)))
    if file_type:
        q = q.filter(Document.file_type == file_type)
    if status:
        q = q.filter(Document.status == status)
    total = q.count()
    docs = q.order_by(Document.create_time.desc(), Document.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    user_map = _user_name_map(db, [d.upload_user_id for d in docs])
    dept_map = _dept_name_map(db, [d.dept_id for d in docs])
    items = [
        {
            "id": d.id,
            "doc_name": d.doc_name,
            "origin_file_name": d.origin_file_name,
            "file_type": d.file_type,
            "file_size": d.file_size,
            "version_no": d.version_no,
            "status": d.status,
            "progress": d.progress,
            "dept_id": d.dept_id,
            "dept_name": dept_map.get(d.dept_id),
            "uploader": user_map.get(d.upload_user_id),
            "create_time": d.create_time,
            "update_time": d.update_time,
        }
        for d in docs
    ]
    return ok(data={"total": total, "items": items})


# ---------- 会话总览 ----------
@router.get("/conversations")
def admin_list_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    keyword: str = "",
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    q = db.query(Conversation)
    if keyword:
        q = q.filter(Conversation.title.like(f"%{keyword}%"))
    total = q.count()
    convs = q.order_by(Conversation.update_time.desc(), Conversation.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    user_map = _user_name_map(db, [c.user_id for c in convs])
    conv_ids = [c.id for c in convs]
    # P1-7：原实现按会话逐条 count 消息（N+1），改为一次 IN + GROUP BY 批量统计
    msg_counts: dict[int, int] = {}
    if conv_ids:
        msg_counts = dict(
            db.query(ConversationMsg.conv_id, func.count(ConversationMsg.id))
            .filter(ConversationMsg.conv_id.in_(conv_ids))
            .group_by(ConversationMsg.conv_id)
            .all()
        )
    items = [
        {
            "id": c.id,
            "title": c.title,
            "user_id": c.user_id,
            "username": user_map.get(c.user_id),
            "msg_count": msg_counts.get(c.id, 0),
            "is_context_reset": c.is_context_reset,
            "create_time": c.create_time,
            "update_time": c.update_time,
        }
        for c in convs
    ]
    return ok(data={"total": total, "items": items})


# ---------- 用户反馈管理 ----------
@router.get("/feedback")
def admin_list_feedback(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: str = "",
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    q = db.query(Feedback)
    if status:
        q = q.filter(Feedback.status == status)
    total = q.count()
    fbs = q.order_by(Feedback.create_time.desc(), Feedback.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    user_map = _user_name_map(db, [f.user_id for f in fbs])
    msg_ids = [f.msg_id for f in fbs]
    msg_map: dict[int, tuple[int | None, str]] = {}
    if msg_ids:
        for m in db.query(ConversationMsg).filter(ConversationMsg.id.in_(msg_ids)).all():
            msg_map[m.id] = (m.conv_id, m.content[:200])
    items = [
        {
            "id": f.id,
            "msg_id": f.msg_id,
            "user_id": f.user_id,
            "username": user_map.get(f.user_id),
            "score": f.score,
            "content": f.content,
            "status": f.status,
            "create_time": f.create_time,
            "msg_conv_id": msg_map.get(f.msg_id, (None, None))[0],
            "msg_preview": msg_map.get(f.msg_id, (None, None))[1],
        }
        for f in fbs
    ]
    return ok(data={"total": total, "items": items})


@router.post("/feedback/{feedback_id}/handle")
def handle_feedback(feedback_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    fb = db.get(Feedback, feedback_id)
    if not fb:
        raise BizError(NOT_FOUND, "反馈不存在")
    fb.status = "handled"
    db.commit()
    return ok(message="反馈已处理")


# ---------- 角色权限总览 ----------
@router.get("/role-overview")
def role_overview(
    keyword: str = Query(""),
    only_custom: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """全平台团队角色权限总览：内置三档 + 各团队自定义角色，附成员数统计。

    只读汇总接口，角色的增删改仍在团队详情的「角色权限」页签内完成。
    P1-8：原实现一次性拉全表团队并展开成 items（团队数增长后无上限），改为按团队分页；
    不传分页参数时返回第一页，total 仍为全量条目真实总数，向后兼容。
    """
    from app.api.org_extra import BUILTIN_ROLE_PERMS, PERM_CATALOG

    team_q = db.query(Team)
    if keyword:
        team_q = team_q.filter(Team.name.contains(keyword))
    team_total = team_q.count()
    teams = (
        team_q.order_by(Team.id.asc()).offset((page - 1) * page_size).limit(page_size).all()
    )
    team_ids = [t.id for t in teams]

    # 全量自定义角色数（不受分页影响，供前端校验总数）
    custom_total_q = db.query(func.count(TeamRole.id)).join(Team, Team.id == TeamRole.team_id)
    if keyword:
        custom_total_q = custom_total_q.filter(Team.name.contains(keyword))
    custom_total = custom_total_q.scalar() or 0

    count_map = {}
    custom_map = {}
    if team_ids:
        rows = (
            db.query(TeamMember.team_id, TeamMember.role, func.count(TeamMember.id))
            .filter(TeamMember.team_id.in_(team_ids))
            .group_by(TeamMember.team_id, TeamMember.role)
            .all()
        )
        for tid, role_key, cnt in rows:
            count_map[(tid, role_key)] = cnt
        for r in db.query(TeamRole).filter(TeamRole.team_id.in_(team_ids)).order_by(TeamRole.id.asc()).all():
            custom_map.setdefault(r.team_id, []).append(r)

    builtin_names = {"owner": "所有者", "admin": "管理员", "member": "成员"}
    items = []
    for t in teams:
        if not only_custom:
            for key in ("owner", "admin", "member"):
                perms = BUILTIN_ROLE_PERMS.get(key, [])
                items.append(
                    {
                        "team_id": t.id,
                        "team_name": t.name,
                        "role_key": key,
                        "role_name": builtin_names[key],
                        "built_in": True,
                        "editable": False,
                        "perms": perms,
                        "perm_count": len(perms),
                        "member_count": count_map.get((t.id, key), 0),
                        "remark": "内置角色，权限固定不可编辑",
                    }
                )
        for r in custom_map.get(t.id, []):
            perms = r.perms or []
            items.append(
                {
                    "team_id": t.id,
                    "team_name": t.name,
                    "role_key": r.role_key,
                    "role_name": r.role_name,
                    "built_in": False,
                    "editable": True,
                    "perms": perms,
                    "perm_count": len(perms),
                    "member_count": count_map.get((t.id, r.role_key), 0),
                    "remark": r.remark or "",
                }
            )

    builtin_total = 0 if only_custom else team_total * 3
    return ok(
        data={
            "catalog": PERM_CATALOG,
            "items": items,
            "total": builtin_total + custom_total,
            "team_total": team_total,
            "custom_total": custom_total,
            "perm_total": len(PERM_CATALOG),
            "page": page,
            "page_size": page_size,
            "page_items": len(items),
        }
    )
