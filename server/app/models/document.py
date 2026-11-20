# -*- coding: utf-8 -*-
"""文档、标签、标签关系、文档切片。"""
# ===== 逐行注释：文档域数据模型（四张表） =====
# 1. Document（文档主表）：记录元信息（名称/原始名/类型/大小/hash）、归属部门与上传人、
#    解析状态机（status: pending/processing/success/failed + progress 百分比 + fail_msg 失败原因）、
#    OCR 内容、Excel sheet 信息、LLM 摘要、GraphRAG 抽取状态（kg_status + 实体/关系计数）、
#    热度统计（view_count 浏览量 / retrieve_count 检索命中数，供智能看板排序）、
#    版本号（version_no，同一 origin_file_name 上传新文件自动 +1）与软删除标记 is_deleted。
# 2. DocTag / DocTagRel：标签主表 + 文档-标签多对多关系表（UniqueConstraint 防重复打标）。
# 3. DocChunk（切片表）：解析后的文本切片，page_no 页码/sheet_name 工作表定位，chunk_index 顺序，
#    chroma_id 与向量库条目关联（RAG 检索命中后回查原文段落）。
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Document(Base):
    __tablename__ = "document"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doc_name: Mapped[str] = mapped_column(String(255), nullable=False)
    origin_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(32), nullable=False)  # pdf/scan_pdf/excel/word/ppt/txt/md/image
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    dept_id: Mapped[int] = mapped_column(Integer, ForeignKey("department.id"), nullable=False)
    upload_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    parent_doc_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/processing/success/failed
    progress: Mapped[int] = mapped_column(Integer, default=0)
    fail_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ocr_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    excel_sheet_info: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    extract_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 知识图谱（GraphRAG）抽取状态与统计
    kg_status: Mapped[str] = mapped_column(String(16), default="none")  # none/processing/success/failed
    kg_entity_count: Mapped[int] = mapped_column(Integer, default=0)
    kg_relation_count: Mapped[int] = mapped_column(Integer, default=0)
    kg_error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    kg_finish_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 文档热度（功能四 智能看板）：浏览量 + 检索命中
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    retrieve_count: Mapped[int] = mapped_column(Integer, default=0)
    create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    update_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class DocTag(Base):
    __tablename__ = "doc_tag"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tag_name: Mapped[str] = mapped_column(String(64), nullable=False)
    create_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("user.id"), nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class DocTagRel(Base):
    __tablename__ = "doc_tag_rel"
    __table_args__ = (UniqueConstraint("doc_id", "tag_id", name="uq_doc_tag"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doc_id: Mapped[int] = mapped_column(Integer, ForeignKey("document.id"), nullable=False)
    tag_id: Mapped[int] = mapped_column(Integer, ForeignKey("doc_tag.id"), nullable=False)


class DocChunk(Base):
    __tablename__ = "doc_chunk"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doc_id: Mapped[int] = mapped_column(Integer, ForeignKey("document.id"), nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    page_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sheet_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    chroma_id: Mapped[str] = mapped_column(String(64), nullable=False)

# ===== 逐行注释：双写补偿表（关系库已删 / 向量库删除失败） =====
# 1. 场景：永久删除文档时关系库事务先提交，向量库（Chroma）删除失败会留下孤儿向量，
#    导致已删文档仍被 RAG 命中（越权泄露隐患）。
# 2. 做法：删除失败即在本表登记 doc_id，启动钩子 reconcile_vector_orphans 定期重试删除，
#    成功后删除登记行；以关系库为准，向量库最终追上（最终一致）。
class VectorOrphan(Base):
    __tablename__ = "vector_orphan"

    doc_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    update_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
