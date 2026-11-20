# -*- coding: utf-8 -*-
"""Agent 任务模型。"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentTaskReq(BaseModel):
    task_type: str = Field(pattern="^(weekly_report|doc_compare|write_plan)$")
    doc_ids: list[int] = Field(default_factory=list, max_length=50)
    params: dict[str, Any] = Field(default_factory=dict)
    model_provider_id: int | None = None  # 指定模型供应商；不传则使用默认供应商/环境变量
    schedule_type: str = Field("once", pattern="^(once|daily|weekly)$")  # 周期任务：once 一次性 / daily 每日 / weekly 每周
    schedule_cron: str | None = Field(default=None, max_length=64)  # 如 daily "30 9 * * *"、weekly "0 9 * * 1"
    template_id: int | None = None  # 来源模板
    notify_on_finish: bool = True  # 完成后发送通知
    canvas_json: str | None = None  # 拖拽式工作流编排画布 JSON（nodes/edges）


class AgentTaskResp(BaseModel):
    task_id: int
    task_type: str | None = None
    status: str
    need_confirm: bool = False
    selected_doc_ids: list[int] | None = None
    params: dict[str, Any] | None = None
    retrieval_chunks: list[dict[str, Any]] = []
    web_sources: list[dict[str, Any]] | None = None
    workflow_trace: list[dict[str, Any]] | None = None
    task_result: str | None = None
    create_time: str | None = None
    finish_time: str | None = None
    error_msg: str | None = None
    schedule_type: str = "once"
    schedule_cron: str | None = None
    template_id: int | None = None
    notify_on_finish: bool = True
    canvas_json: str | None = None  # 拖拽式工作流编排画布 JSON（nodes/edges）


class AgentConfirmReq(BaseModel):
    confirm: bool


class AgentTemplateReq(BaseModel):
    """任务模板：保存任务配置并可定时周期执行。"""
    template_name: str = Field(min_length=1, max_length=64)
    task_type: str = Field(pattern="^(weekly_report|doc_compare|write_plan)$")
    doc_ids: list[int] = Field(default_factory=list, max_length=50)
    params: dict[str, Any] = Field(default_factory=dict)
    model_provider_id: int | None = None
    schedule_type: str = Field("once", pattern="^(once|daily|weekly)$")
    schedule_cron: str | None = Field(default=None, max_length=64)
    notify_on_finish: bool = True
    canvas_json: str | None = None  # 画布 JSON（nodes/edges）


class AgentTemplateResp(BaseModel):
    id: int
    template_name: str
    task_type: str
    selected_doc_ids: list[int] | None = None
    params: dict[str, Any] | None = None
    canvas_json: str | None = None
    schedule_type: str = "once"
    schedule_cron: str | None = None
    notify_on_finish: bool = True
    create_time: datetime
    update_time: datetime
