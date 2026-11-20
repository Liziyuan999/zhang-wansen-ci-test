# -*- coding: utf-8 -*-
"""模型供应商接口模型。"""
from pydantic import BaseModel, Field


class ProviderCreateReq(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    base_url: str = Field(min_length=1, max_length=255)
    model: str = Field(min_length=1, max_length=128)
    api_key: str = Field(default="", max_length=512)
    is_default: bool = False
    enabled: bool = True


class ProviderUpdateReq(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    base_url: str | None = Field(default=None, min_length=1, max_length=255)
    model: str | None = Field(default=None, min_length=1, max_length=128)
    # api_key 留空（None 或 ""）表示不覆盖原值
    api_key: str | None = Field(default=None, max_length=512)
    is_default: bool | None = None
    enabled: bool | None = None
