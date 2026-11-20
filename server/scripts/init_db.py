# -*- coding: utf-8 -*-
"""初始化数据库表（幂等）。用法：python scripts/init_db.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.indexes import ensure_indexes, list_indexes  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.models import *  # noqa: F401,F403,E402

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    created = ensure_indexes(engine)
    print(f"数据库初始化完成: {settings.DATABASE_URL}")
    print("已创建表:", ", ".join(sorted(Base.metadata.tables.keys())))
    print(f"索引补齐: 本次执行 {len(created)} 条 DDL（IF NOT EXISTS，已存在则跳过）")
    print("当前业务索引:", ", ".join(list_indexes(engine)))
