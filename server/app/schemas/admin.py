# -*- coding: utf-8 -*-
"""管理员后台模型。"""
from typing import Any

from pydantic import BaseModel, Field


class DeptCreateReq(BaseModel):
    dept_name: str = Field(min_length=1, max_length=64)
    parent_id: int | None = Field(default=None, ge=1)
    leader_id: int | None = Field(default=None, ge=1)
    description: str | None = Field(default=None, max_length=255)
    sort_order: int = Field(default=0, ge=0, le=9999)


class DeptUpdateReq(BaseModel):
    dept_name: str | None = Field(default=None, min_length=1, max_length=64)
    parent_id: int | None = Field(default=None, ge=1)
    leader_id: int | None = Field(default=None, ge=1)
    description: str | None = Field(default=None, max_length=255)
    sort_order: int | None = Field(default=None, ge=0, le=9999)


class AdminUserUpdateReq(BaseModel):
    role: str | None = Field(default=None, pattern="^(staff|admin)$")
    status: str | None = Field(default=None, pattern="^(active|disabled)$")
    dept_id: int | None = None
    username: str | None = Field(default=None, min_length=2, max_length=32)


class ConfigUpdateReq(BaseModel):
    config_key: str = Field(min_length=1, max_length=128)
    config_value: str
    description: str | None = None
