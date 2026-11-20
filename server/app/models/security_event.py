# -*- coding: utf-8 -*-
"""账号安全事件：登录、2FA 开关、密码修改、头像变更等留痕。"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SecurityEvent(Base):
    __tablename__ = "security_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)  # login/2fa_enable/2fa_disable/password_change/avatar_change/...
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
