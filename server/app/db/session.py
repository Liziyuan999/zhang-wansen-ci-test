# -*- coding: utf-8 -*-
"""数据库引擎与会话工厂。

P1-1 修复（并发安全）：
1. journal_mode=WAL：写事务不再阻塞读，文档解析写入切片/向量期间，列表与检索查询不会
   因排他锁被挂起，多用户并发时不再出现 "database is locked"。
2. busy_timeout=10000（10s）：写锁冲突时由 SQLite 内部等待重试，而不是立刻抛
   OperationalError；配合 WAL 覆盖"两个写事务同时提交"的短时争抢。
3. synchronous=NORMAL：WAL 模式下的推荐值，兼顾持久性与写入吞吐（掉电最多丢最后一次提交）。
注意：journal_mode 持久化在库文件内（只需生效一次），busy_timeout / synchronous 是"每连接"
属性，必须通过 connect 事件逐连接设置，否则连接池新建连接会丢失配置。
"""
import logging

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)

# SQLite 写锁等待时长（毫秒）：与下方 connect_args.timeout（秒）保持一致
SQLITE_BUSY_TIMEOUT_MS = 10000

connect_args = {}
IS_SQLITE = settings.DATABASE_URL.startswith("sqlite")
if IS_SQLITE:
    # timeout 是 sqlite3 驱动的忙等待秒数（等价于 busy_timeout 的驱动级配置）
    connect_args = {"check_same_thread": False, "timeout": SQLITE_BUSY_TIMEOUT_MS / 1000}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)


def _apply_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
    """每条新连接强制应用 PRAGMA，保证连接池内连接口径一致。"""
    try:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
            cursor.execute("PRAGMA synchronous=NORMAL")
        finally:
            cursor.close()
    except Exception as exc:  # pragma: no cover - PRAGMA 失败不应阻断服务启动
        logger.warning("SQLite PRAGMA 应用失败（降级为默认模式）: %s", exc)


if IS_SQLITE:
    event.listen(engine, "connect", _apply_sqlite_pragmas)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
