# -*- coding: utf-8 -*-
"""团队、团队成员、团队邀请。"""
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Team(Base):
    __tablename__ = "team"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 上级团队/部门（组织架构树）
    create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class TeamMember(Base):
    __tablename__ = "team_member"
    __table_args__ = (UniqueConstraint("team_id", "user_id", name="uq_team_member_team_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("team.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(16), default="member", nullable=False)  # owner/admin/member
    perms: Mapped[list | None] = mapped_column(JSON, nullable=True)  # 细粒度权限位：manage_docs/manage_members/send_notice/view_audit
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class TeamInvitation(Base):
    __tablename__ = "team_invitation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("team.id"), nullable=False)
    inviter_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(128), nullable=False)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class TeamNotice(Base):
    """团队通知：owner/admin 向团队全体成员发布。"""

    __tablename__ = "team_notice"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("team.id"), nullable=False)
    sender_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    content: Mapped[str] = mapped_column(String(1000), nullable=False)
    create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class TeamNoticeRead(Base):
    """通知已读记录：每个成员一条，标志该成员已读某条通知。"""

    __tablename__ = "team_notice_read"
    __table_args__ = (UniqueConstraint("notice_id", "user_id", name="uq_notice_read_notice_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    notice_id: Mapped[int] = mapped_column(Integer, ForeignKey("team_notice.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    read_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class TeamLog(Base):
    """团队动态/操作日志：成员加入、角色变更、邀请发送、退出、解散等留痕。"""

    __tablename__ = "team_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("team.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(String(255), nullable=False)
    create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
