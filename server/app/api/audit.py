# -*- coding: utf-8 -*-
"""审计日志查询接口（管理视角）：按操作类型/操作人/时间范围过滤 + 分页。"""
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_admin
from app.core.response import ok
from app.models import OperationLog, User
from app.services.audit import action_label, module_label

router = APIRouter(prefix="/api/audit", tags=["审计日志"])

# 各业务模块可用的动作筛选项（与 operation_log.action 存储值对应）
MODULE_ACTIONS: dict[str, list[str]] = {
    "auth": ["login", "logout", "register", "refresh"],
    "user": ["GET", "POST", "PUT", "PATCH", "DELETE", "update-profile", "change-password"],
    "document": ["GET", "POST", "PUT", "DELETE", "upload", "download"],
    "chat": ["GET", "POST", "search", "ask"],
    "agent": ["GET", "POST", "DELETE", "run", "retry"],
    "team": ["GET", "POST", "PUT", "DELETE", "invite", "join", "leave"],
    "notice": ["GET", "POST", "PUT", "DELETE"],
    "admin": ["GET", "POST", "PUT", "DELETE"],
    "audit": ["GET", "POST", "generate"],
    "dashboard": ["GET"],
    "report": ["GET", "POST", "generate"],
}


@router.get("/modules")
def list_modules(_: User = Depends(require_admin)):
    """返回操作分类枚举（前端下拉用）：[{module, module_label, actions}]。"""
    from app.services.audit import MODULE_LABELS

    items = [{"module": k, "module_label": v, "actions": MODULE_ACTIONS.get(k, ["GET", "POST", "PUT", "DELETE"])} for k, v in MODULE_LABELS.items()]
    return ok(data=items)


@router.get("/logs")
def list_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    module: str = Query("", description="操作类型（业务分类，如 chat/agent/team/document）"),
    action: str = Query("", description="动作（login/GET/POST/DELETE 等）"),
    operator: str = Query("", description="操作人用户名模糊匹配"),
    start: str = Query("", description="开始时间 ISO，如 2026-10-20"),
    end: str = Query("", description="结束时间 ISO，如 2026-10-27"),
    status: str = Query("", description="success/fail"),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    q = db.query(OperationLog)
    if module:
        q = q.filter(OperationLog.module == module)
    if action:
        q = q.filter(OperationLog.action == action)
    if operator:
        q = q.filter(OperationLog.username.contains(operator))
    if status:
        q = q.filter(OperationLog.status == status)
    if start:
        try:
            q = q.filter(OperationLog.create_time >= datetime.fromisoformat(start))
        except ValueError:
            pass
    if end:
        try:
            q = q.filter(OperationLog.create_time < datetime.fromisoformat(end))
        except ValueError:
            pass
    total = q.count()
    logs = q.order_by(OperationLog.create_time.desc(), OperationLog.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = [
        {
            "id": l.id,
            "user_id": l.user_id,
            "username": l.username,
            "dept_id": l.dept_id,
            "action": l.action,
            "action_label": action_label(l.action),
            "module": l.module,
            "module_label": module_label(l.module),
            "method": l.method,
            "path": l.path,
            "detail": l.detail,
            "ip": l.ip,
            "status": l.status,
            "duration_ms": l.duration_ms,
            "create_time": l.create_time.isoformat(sep=" ") if l.create_time else "",
        }
        for l in logs
    ]
    return ok(data={"total": total, "items": items})
