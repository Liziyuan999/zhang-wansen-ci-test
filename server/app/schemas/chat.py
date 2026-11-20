# -*- coding: utf-8 -*-
"""对话/溯源/反馈模型。"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ChatReq(BaseModel):
    conv_id: int | None = None
    question: str = Field(min_length=1, max_length=4000)
    web_search: bool = False  # 联网检索开关：开启时融合实时网络结果
    model_provider_id: int | None = None  # 指定模型供应商；不传则使用默认供应商/环境变量
    doc_ids: list[int] | None = None  # 参考文档精确限定检索；为空则检索整个部门知识库


class ChatResp(BaseModel):
    conv_id: int
    msg_id: int
    answer: str
    citations: list[dict[str, Any]] = []
    web_sources: list[dict[str, Any]] | None = None  # 联网检索来源 [{title,url,snippet}]，空则省略
    tokens: dict[str, int] | None = None


class FeedbackReq(BaseModel):
    msg_id: int
    score: str = Field(pattern="^(good|bad)$")
    content: str | None = Field(default=None, max_length=2000)


class MsgItem(BaseModel):
    id: int
    role: str
    content: str
    ref_chunk_ids: list | None = None
    create_time: datetime


class ConvItem(BaseModel):
    id: int
    title: str
    create_time: datetime
    update_time: datetime


class RenameConvReq(BaseModel):
    title: str = Field(min_length=1, max_length=50)


class ConvDetail(BaseModel):
    conv: ConvItem
    messages: list[MsgItem]
