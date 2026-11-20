# -*- coding: utf-8 -*-
"""演示模式接口：POST /api/demo/seed、GET /api/demo/status、POST /api/demo/clear。"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_admin
from app.core.response import ok
from app.models import User
from app.services.demo_service import clear_demo, demo_status, seed_demo

router = APIRouter(prefix="/api/demo", tags=["演示模式"])


class SeedReq(BaseModel):
    keep_original: bool = Field(True, description="是否保留原有数据（False 时先清除演示数据再灌入）")


# ===== 逐行注释：演示模式路由层 =====
# 1. POST /seed：灌入演示部门/成员/文档/知识关系/对话数据；keep_original=True 保留真实数据，
#    演示数据带独立标记（如用户名/部门名前缀），保证与真实数据隔离；
# 2. GET /status：返回演示模式是否开启、灌入时间与各类型数量（前端状态条展示）；
# 3. POST /clear：仅删除带演示标记的数据，真实数据不受影响，实现"一键清除恢复"。
@router.post("/seed")
def demo_seed(req: SeedReq, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    data = seed_demo(db, keep_original=req.keep_original)
    return ok(data=data, message="演示数据已灌入，可前往知识图谱 / Agent 工作流 / 数据看板参观")


@router.get("/status")
def demo_status_api(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(data=demo_status(db))


@router.post("/clear")
def demo_clear(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    data = clear_demo(db)
    return ok(data=data, message="演示数据已清除，真实数据不受影响")
