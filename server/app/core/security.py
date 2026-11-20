# -*- coding: utf-8 -*-
"""密码哈希与 JWT 工具。"""
import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


# ===== 逐行注释：密码哈希与 JWT 双 token 工具 =====
# 1. hash_password / verify_password：基于 bcrypt 加盐哈希，不存明文密码；
# 2. _create_token：统一生成 JWT，载荷含 sub（用户 ID）、type（access/refresh 双 token 区分）、
#    jti（唯一 ID 防重放）、iat（签发时间）、exp（过期时间）；签名算法与密钥来自 settings；
# 3. create_access_token：短期 token（分钟级），随每次请求携带；
# 4. create_refresh_token：长期 token（天级），用于刷新 access token 保持登录态；
# 5. decode_token：解析并校验签名/过期，失败返回 None（上层据此判 401）；
# 6. hash_token：对 refresh_token 等长令牌做 SHA-256 哈希后入库，数据库不存明文令牌。
def _create_token(user_id: int, token_type: str, expire_minutes: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + timedelta(minutes=expire_minutes),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: int) -> str:
    return _create_token(user_id, "access", settings.ACCESS_TOKEN_EXPIRE_MINUTES)


def create_refresh_token(user_id: int) -> str:
    return _create_token(user_id, "refresh", settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None


def hash_token(token: str) -> str:
    """对长令牌（如 refresh_token）做 SHA-256 哈希，数据库不存明文。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
