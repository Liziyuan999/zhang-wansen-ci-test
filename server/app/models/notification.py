# -*- coding: utf-8 -*-
"""全局用户通知：系统/任务/动态通知中心闭环。"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserNotification(Base):
    """面向个人的全局通知：Agent 任务完成、系统消息等，与团队通知并列。"""

    __tablename__ = "user_notification"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    content: Mapped[str] = mapped_column(String(1000), nullable=False)
    ntype: Mapped[str] = mapped_column(String(32), default="system")  # system/agent/team
    category: Mapped[str] = mapped_column(String(32), default="system")  # team=团队动态 / approval=审批消息 / system=系统消息
    related_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 关联业务 ID（任务/团队等）
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
