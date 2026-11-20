# -*- coding: utf-8 -*-
"""团队通知相关请求/响应模型。"""
from pydantic import BaseModel, Field


class SendNoticeReq(BaseModel):
    team_id: int
    title: str = Field(min_length=1, max_length=128)
    content: str = Field(min_length=1, max_length=1000)


class NoticeResp(BaseModel):
    id: int
    team_id: int
    team_name: str
    sender_id: int
    sender_name: str
    title: str
    content: str
    create_time: str
    direction: str  # sent=我发送的 / received=我接收的
    read: bool | None = None  # 接收者：是否已读；发送者：None（不参与未读计数）
