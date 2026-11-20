# -*- coding: utf-8 -*-
"""知识图谱接口：实体抽取 / 图谱数据 / 实体搜索 / 图谱统计。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.response import ok
from app.models import User
from app.services import kg_service

router = APIRouter(prefix="/api/kg", tags=["知识图谱"])


# ===== 逐行注释：知识图谱路由层 =====
# 1. 统一前缀 /api/kg，全部接口经 get_current_user 校验 JWT 后注入当前用户；
# 2. extract：POST 手动触发某文档的实体/关系抽取，返回实体数/关系数统计供前端提示；
# 3. graph：GET 返回 nodes+links，节点带 degree（度数）供前端力导向布局按度数定半径/向心力；
#    doc_id 过滤单文档、keyword 过滤实体名、limit 上限 1000 控制返回规模；
# 4. search：GET 按名称模糊匹配实体（前端"搜索实体"输入框使用），limit 默认 20；
# 5. stats：GET 返回实体总数/关系总数/已抽取文档数/类型分布，驱动图谱页统计卡片与类型条。
@router.post("/extract/{doc_id}")
def extract_doc(doc_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """手动触发文档实体/关系抽取，返回抽取统计。"""
    stats = kg_service.extract_document_kg(db, user, doc_id)
    return ok(data=stats, message=f"抽取完成：实体 {stats['entities']} 个，关系 {stats['relations']} 条")


@router.get("/graph")
def get_graph(
    doc_id: int | None = Query(None, description="按文档过滤"),
    keyword: str | None = Query(None, description="按实体名称关键词过滤"),
    limit: int = Query(200, ge=1, le=1000),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """图谱数据：nodes + links（节点含度数便于前端布局）。"""
    return ok(data=kg_service.get_graph(db, user, doc_id=doc_id, keyword=keyword, limit=limit))


@router.get("/search")
def search(
    keyword: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """实体搜索：按名称模糊匹配。"""
    return ok(data=kg_service.search_entities(db, user, keyword, limit))


@router.get("/stats")
def stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """图谱统计：实体数 / 关系数 / 已抽取文档数 / 类型分布。"""
    return ok(data=kg_service.get_stats(db, user))
