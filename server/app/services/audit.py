# -*- coding: utf-8 -*-
"""审计日志：请求中间件记录 operation_log + 业务显式审计帮助函数。"""
import logging
import time
from typing import Any

from fastapi import Request

logger = logging.getLogger(__name__)

SKIP_PATHS = {"/api/auth/send-code", "/api/auth/register", "/api/auth/login", "/api/auth/refresh"}

# 业务模块 → 中文分类（前端管理视角展示用）
MODULE_LABELS: dict[str, str] = {
    "auth": "登录认证",
    "user": "用户管理",
    "document": "文档操作",
    "chat": "检索对话",
    "agent": "Agent 任务",
    "team": "组织/团队",
    "notice": "团队通知",
    "admin": "系统管理",
    "audit": "审计日志",
    "dashboard": "数据看板",
    "report": "AI 周报",
}

# HTTP 方法 → 中文动作
ACTION_LABELS: dict[str, str] = {
    "GET": "查询",
    "POST": "创建/提交",
    "PUT": "更新",
    "PATCH": "修改",
    "DELETE": "删除",
}


def module_label(module: str) -> str:
    return MODULE_LABELS.get(module, module or "系统")


def action_label(action: str) -> str:
    return ACTION_LABELS.get(action, action)


def record_audit(
    db,
    user,
    action: str,
    module: str,
    detail: str | None = None,
    ip: str = "",
    status: str = "success",
    duration_ms: int = 0,
) -> None:
    # ===== 逐行注释：业务显式审计写入 =====
    # 1. 供业务代码主动记录语义化操作（登录、上传、下载审批、退出审批等），
    #    与 audit_middleware 的自动请求级日志互补；
    # 2. 写入 OperationLog：用户/部门/动作/模块/详情/IP/状态/耗时，前端审计页可检索；
    # 3. 写库失败仅告警不阻断业务主流程（日志为旁路能力）。
    """业务侧显式写审计日志（登录、上传、删除等需要语义化 action 的场景）。"""
    try:
        from app.models import OperationLog

        db.add(
            OperationLog(
                user_id=user.id if user else None,
                username=getattr(user, "username", None),
                dept_id=getattr(user, "dept_id", None),
                action=action,
                module=module,
                method="",
                path="",
                detail=detail,
                ip=ip,
                status=status,
                duration_ms=duration_ms,
            )
        )
        db.commit()
    except Exception as exc:  # pragma: no cover
        logger.warning("写入业务审计日志失败: %s", exc)
        db.rollback()


def audit_middleware(get_db_session, get_user_from_token):
    """生成审计中间件。get_user_from_token: credentials -> User | None。"""

    async def middleware(request: Request, call_next):
        start = time.monotonic()
        response = None
        user = None
        try:
            auth = request.headers.get("authorization", "")
            if auth.lower().startswith("bearer "):
                user = get_user_from_token(auth[7:])
            response = await call_next(request)
            return response
        finally:
            duration_ms = int((time.monotonic() - start) * 1000)
            if request.url.path.startswith("/api") and request.url.path not in SKIP_PATHS:
                try:
                    db = get_db_session()
                    from app.models import OperationLog

                    uid = user.id if user else None
                    uname = user.username if user else None
                    dept_id = user.dept_id if user else None
                    segs = request.url.path.split("/")
                    module = segs[2] if len(segs) > 2 else ""
                    db.add(
                        OperationLog(
                            user_id=uid,
                            username=uname,
                            dept_id=dept_id,
                            action=request.method,
                            module=module,
                            method=request.method,
                            path=request.url.path,
                            ip=request.client.host if request.client else "",
                            status="success" if not response or response.status_code < 400 else "fail",
                            duration_ms=duration_ms,
                        )
                    )
                    db.commit()
                except Exception as exc:  # pragma: no cover
                    logger.warning("写入审计日志失败: %s", exc)
                finally:
                    db.close()

    return middleware
