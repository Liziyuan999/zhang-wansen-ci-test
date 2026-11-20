# -*- coding: utf-8 -*-
"""部门表（企业级组织架构）。"""
# ===== 逐行注释：部门数据模型（组织架构树） =====
# 1. dept_name：部门名称（唯一用于注册时按名称归属部门，如"研发部"）。
# 2. parent_id：上级部门 ID（自引用树），支撑多级组织架构（公司 -> 中心 -> 部门）。
# 3. leader_id：部门负责人（关联 user.id，可空），用于审批流"部门负责人审批"环节。
# 4. sort_order：同级部门排序权重（升序），控制组织中心/下拉框展示顺序。
# 5. create_time：创建时间。
from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Department(Base):
    __tablename__ = "department"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dept_name: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 上级部门（组织架构树）
    leader_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 部门负责人（关联 user.id，可空）
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)  # 部门描述
    sort_order: Mapped[int] = mapped_column(Integer, default=0)  # 排序权重（同级升序）
    create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
