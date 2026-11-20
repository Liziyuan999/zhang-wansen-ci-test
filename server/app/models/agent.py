# -*- coding: utf-8 -*-
"""Agent 任务表 与 任务模板表。"""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AgentTask(Base):
    __tablename__ = "agent_task"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    task_type: Mapped[str] = mapped_column(String(32), nullable=False)  # weekly_report/doc_compare/write_plan
    selected_doc_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    params: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # 任务补充参数（如周期/关注点）
    retrieval_chunks: Mapped[list | None] = mapped_column(JSON, nullable=True)
    web_sources: Mapped[list | None] = mapped_column(JSON, nullable=True)  # 联网检索来源 [{title,url,snippet}]
    workflow_trace: Mapped[list | None] = mapped_column(JSON, nullable=True)  # LangGraph 工作流节点轨迹 [{node,name,status,summary,cost_ms}]
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    task_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="retrieving")  # retrieving/waiting_confirm/finished/failed/cancelled
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 来源模板 ID
    canvas_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # 拖拽式工作流编排画布 JSON (nodes/edges)
    schedule_type: Mapped[str] = mapped_column(String(16), default="once")  # once/daily/weekly
    schedule_cron: Mapped[str | None] = mapped_column(String(64), nullable=True)  # cron 表达式（如 0 9 * * 1）
    notify_on_finish: Mapped[bool] = mapped_column(Boolean, default=True)  # 完成后通知
    notified: Mapped[bool] = mapped_column(Boolean, default=False)  # 是否已通知
    create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    finish_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AgentTemplate(Base):
    """Agent 任务模板：预置任务类型/参数/定时/通知配置，一键创建定时任务。"""

    __tablename__ = "agent_template"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    template_name: Mapped[str] = mapped_column(String(64), nullable=False)
    task_type: Mapped[str] = mapped_column(String(32), nullable=False)  # weekly_report/doc_compare/write_plan
    selected_doc_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    canvas_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # 鎷栨嫿寮忓伐浣滄祦缂栨帓鐢诲竵 JSON (nodes/edges)
    schedule_type: Mapped[str] = mapped_column(String(16), default="once")  # once/daily/weekly
    schedule_cron: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notify_on_finish: Mapped[bool] = mapped_column(Boolean, default=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    update_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
