# -*- coding: utf-8 -*-
"""用户、刷新令牌、邮箱验证码。"""
# ===== 逐行注释：认证域数据模型（三张表） =====
# 1. User（用户表）：唯一用户名/邮箱 + bcrypt 密码哈希；role（staff/admin）与 dept_id 关联组织；
#    status 控制可用性（active/禁用）；totp_secret/totp_enabled 为 2FA 预留；
#    login_fail_count/login_locked_until 实现持久化登录锁定（重启不丢失）；
#    last_login_time 供"最近登录"展示与异地告警参考。
# 2. RefreshToken（刷新令牌表）：只存 token_hash（SHA-256 哈希，不存明文），
#    expires_at 过期时间 + revoked 撤销标记 + user_id 归属；
#    服务端可精确撤销某条 refresh token（logout / 刷新轮换时置位），
#    UniqueConstraint 保证同一哈希唯一，防止同一 token 被重复入库。
# 3. EmailCode（邮箱验证码表）：email + purpose（register/login/reset/unlock）+ code_hash +
#    expires_at + used 一次性使用标记，支撑验证码登录/找回密码/解锁全流程。
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), default="staff")
    dept_id: Mapped[int] = mapped_column(Integer, ForeignKey("department.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active")
    avatar: Mapped[str | None] = mapped_column(String(255), nullable=True)  # 头像 URL/相对路径
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 2FA TOTP 密钥
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)  # 是否已开启 2FA
    # 登录锁定（持久化，重启不丢失）：连续失败 LOGIN_MAX_FAILS 次后锁定 LOGIN_LOCK_MINUTES 分钟
    login_fail_count: Mapped[int] = mapped_column(Integer, default=0)
    login_locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_login_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    update_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class RefreshToken(Base):
    __tablename__ = "refresh_token"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class EmailCode(Base):
    __tablename__ = "email_code"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(128), nullable=False)
    purpose: Mapped[str] = mapped_column(String(32), default="register")
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
