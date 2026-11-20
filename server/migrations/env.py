# -*- coding: utf-8 -*-
"""Alembic 运行环境。

设计要点（P1-5）：
1. 连接串唯一来源：app.core.config.settings.DATABASE_URL（与业务进程完全同源），
   不在 alembic.ini 里硬编码，避免迁移和应用操作到不同库。
2. 引擎复用：默认场景直接复用 app.db.session.engine（含 SQLite WAL / busy_timeout /
   synchronous PRAGMA 与连接池参数），保证迁移与应用在同一连接语义下运行。
   仅当通过 --x db_url=... 或 ALEMBIC_DATABASE_URL 指向其他库（如生成 baseline 时
   使用的空库、CI 临时库）时，才按该 URL 新建 NullPool 引擎。
3. 元数据来源：app.db.base.Base.metadata，并强制 import app.models 触发全部 33 个模型注册。
4. SQLite 兼容：render_as_batch=True，后续对已有表做 ALTER 时自动走"建新表-搬数据-改名"批处理。
5. 路径解析：若传入的是相对 sqlite 路径，统一以 server/ 为基准转绝对路径，
   因此 alembic 命令不必限定在 server 目录下执行。
"""
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import make_url

# server/ 加入 sys.path，保证任意工作目录下都能 import app.*
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.core.config import settings  # noqa: E402
from app.db.base import Base  # noqa: E402
import app.models  # noqa: E402,F401  触发全部模型注册到 Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata

# 27 条业务索引由 app/db/indexes.py 以原生 DDL 维护，未写入 ORM metadata。
# 若不加过滤，autogenerate / alembic check 会把它们视作"库中多出的索引"并生成 drop_index，
# 从而误删应用侧关键索引。此处统一忽略，索引演进由 indexes.py + 后续显式迁移负责。
from app.db.indexes import INDEX_DEFINITIONS  # noqa: E402

BUSINESS_INDEX_NAMES = {name for name, _table, _cols in INDEX_DEFINITIONS}


def _include_object(obj, name, type_, reflected, compare_to):
    if type_ == "index" and reflected and compare_to is None and name in BUSINESS_INDEX_NAMES:
        return False
    return True


SQLITE_PREFIX = "sqlite:///"


def _resolve_url() -> str:
    """优先级：-x db_url=... > 环境变量 ALEMBIC_DATABASE_URL > settings.DATABASE_URL。"""
    url = (
        context.get_x_argument(as_dictionary=True).get("db_url")
        or os.getenv("ALEMBIC_DATABASE_URL")
        or settings.DATABASE_URL
    )
    if url.startswith(SQLITE_PREFIX) and not url.startswith("sqlite:////"):
        raw = url[len(SQLITE_PREFIX):]
        # 仅对"相对路径"做转换；Windows 盘符（E:/...）与 POSIX 绝对路径（/tmp/...）原样保留
        is_abs = raw.startswith("/") or (len(raw) > 1 and raw[1] == ":")
        if raw and raw != ":memory:" and not is_abs:
            url = SQLITE_PREFIX + (BASE_DIR / raw).as_posix()
    return url


def _same_target(app_url, url: str) -> bool:
    """判断目标 URL 是否与应用引擎指向同一数据库。"""
    try:
        ua, ub = make_url(str(app_url)), make_url(url)
    except Exception:
        return False
    if ua.get_backend_name() != ub.get_backend_name():
        return False
    if ua.get_backend_name() == "sqlite" and ua.database and ub.database:
        return Path(str(ua.database)).resolve() == Path(str(ub.database)).resolve()
    return ua.render_as_string(hide_password=False) == ub.render_as_string(hide_password=False)


def _configure(connection=None, url: str | None = None) -> None:
    context.configure(
        connection=connection,
        url=url,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        render_as_batch=True,  # SQLite 下 ALTER 需批处理
        include_schemas=False,
        include_object=_include_object,
        literal_binds=connection is None,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    """离线模式：只输出 SQL（alembic upgrade head --sql）。"""
    _configure(url=_resolve_url())


def run_migrations_online() -> None:
    url = _resolve_url()
    from app.db.session import engine as app_engine

    if _same_target(app_engine.url, url):
        # 默认路径：复用应用引擎（同一套 PRAGMA / 连接池配置）
        with app_engine.connect() as connection:
            _configure(connection=connection)
        return

    section = config.get_section(config.config_ini_section, {}) or {}
    section["sqlalchemy.url"] = url
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        _configure(connection=connection)
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
