# -*- coding: utf-8 -*-
"""会话、会话消息、反馈。"""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Conversation(Base):
    __tablename__ = "conversation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), default="新对话")
    is_context_reset: Mapped[bool] = mapped_column(Boolean, default=False)
    create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    update_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class ConversationMsg(Base):
    __tablename__ = "conversation_msg"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conv_id: Mapped[int] = mapped_column(Integer, ForeignKey("conversation.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user/assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    ref_chunk_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    msg_id: Mapped[int] = mapped_column(Integer, ForeignKey("conversation_msg.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    score: Mapped[str] = mapped_column(String(8), nullable=False)  # good/bad
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/handled
    create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
