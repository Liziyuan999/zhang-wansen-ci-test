# -*- coding: utf-8 -*-
"""文档模块请求/响应模型。"""
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, Field, StringConstraints

# 修复 P2-3：标签名元素级约束（去空格、非空、单个 ≤32 字），配合 list 的 max_length=20，
# 超限时由统一异常处理返回 10001 参数错误，避免 160 字长标签直接入库。
DocTagName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]


class DocListItem(BaseModel):
    id: int
    doc_name: str
    origin_file_name: str
    file_type: str
    file_size: int
    version_no: int
    status: str
    progress: int
    summary: str | None = None
    create_time: datetime
    update_time: datetime
    tags: list[str] = []
    versions: list[int] = []


class DocListResp(BaseModel):
    total: int
    items: list[DocListItem]


class DocDetail(DocListItem):
    file_path: str | None = None
    fail_msg: str | None = None
    ocr_content: str | None = None
    extract_result: dict[str, Any] | None = None


class AssignTagsReq(BaseModel):
    tag_names: list[DocTagName] = Field(default_factory=list, max_length=20)


class UpdateDocMetaReq(BaseModel):
    doc_name: str | None = Field(default=None, min_length=1, max_length=255)
    tag_names: list[DocTagName] | None = Field(default=None, max_length=20)


class BatchDocIdsReq(BaseModel):
    """回收站批量操作：恢复 / 永久删除。"""
    doc_ids: list[int] = Field(min_length=1, max_length=200)


class TrashListItem(DocListItem):
    """回收站条目：额外给出原删除时间（软删未记录专用列，以最后更新时间为近似）。"""
    deleted_time: datetime | None = None
