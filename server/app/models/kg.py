# -*- coding: utf-8 -*-
"""知识图谱：实体 与 实体关系（GraphRAG 双表）。"""
# ===== 逐行注释：知识图谱数据模型（GraphRAG 实体-关系双表） =====
# 1. Entity（实体表）：entity_name 实体名 + entity_type 类型（person/org/product/tech/place/event/other），
#    doc_id/chunk_id 记录来源文档与切片，保证图谱结论可回溯到原文段落。
#    source 标记抽取来源（llm=大模型抽取 / rule=规则抽取）；UniqueConstraint 保证同一文档内实体名唯一。
# 2. EntityRelation（关系表）：source_entity_id -> target_entity_id 有向关系，
#    relation_type 关系名（如"任职于/发布/隶属于"），同样带来源文档/切片与抽取方式字段，
#    支撑图谱可视化（节点=实体，边=关系）与图查询（邻居扩展、路径检索）。
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Entity(Base):
    """知识图谱实体：来源文档与切片可追溯。"""

    __tablename__ = "entity"
    __table_args__ = (UniqueConstraint("entity_name", "doc_id", name="uq_entity_doc"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), default="实体")  # person/org/product/tech/place/event/other
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    doc_id: Mapped[int] = mapped_column(Integer, ForeignKey("document.id"), nullable=False)
    chunk_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(16), default="llm")  # llm/rule
    create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class EntityRelation(Base):
    """实体关系：来源文档与切片可追溯。"""

    __tablename__ = "entity_relation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_entity_id: Mapped[int] = mapped_column(Integer, ForeignKey("entity.id"), nullable=False)
    target_entity_id: Mapped[int] = mapped_column(Integer, ForeignKey("entity.id"), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    doc_id: Mapped[int] = mapped_column(Integer, ForeignKey("document.id"), nullable=False)
    chunk_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(16), default="llm")
    create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
