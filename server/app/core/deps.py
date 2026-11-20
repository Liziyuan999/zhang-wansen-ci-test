# -*- coding: utf-8 -*-
"""FastAPI 依赖：数据库会话、当前用户、管理员校验。"""
from typing import Generator

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.code import NOT_AUTH, NO_PERMISSION
from app.core.response import BizError
from app.db.session import SessionLocal
from app.models import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise BizError(NOT_AUTH, "未登录或 token 无效", status_code=401)
    from app.core.security import decode_token

    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise BizError(NOT_AUTH, "未登录或 token 无效", status_code=401)
    user = db.get(User, int(payload["sub"]))
    if not user or user.status != "active":
        raise BizError(NOT_AUTH, "用户不存在或已禁用", status_code=401)
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise BizError(NO_PERMISSION, "无权限：需要管理员身份")
    return user
