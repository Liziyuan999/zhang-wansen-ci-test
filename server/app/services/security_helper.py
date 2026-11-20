# -*- coding: utf-8 -*-
"""审计中间件用：从 token 解析用户（仅用于日志记录）。"""
from app.core.security import decode_token
from app.db.session import SessionLocal
from app.models import User


def get_user_from_token(token: str):
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return None
    db = SessionLocal()
    try:
        return db.get(User, int(payload["sub"]))
    except Exception:
        return None
    finally:
        db.close()
