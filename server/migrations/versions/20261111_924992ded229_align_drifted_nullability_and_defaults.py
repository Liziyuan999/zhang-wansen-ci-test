# -*- coding: utf-8 -*-
"""align drifted nullability and defaults：把历史 create_all 建出的 12 个"可空+带 server_default"列
对齐到当前 ORM 模型定义（NOT NULL、无 server_default）。

Revision ID: 924992ded229
Revises: cae9dcf72c38
Create Date: 2026-11-11

背景（P1-5 引入 Alembic 后由 `alembic check` 暴露的存量漂移）：
早期版本用 create_all 建库时，下列列声明为 nullable=True 且带 server_default；模型后来收紧为
nullable=False（默认值改由 Python 侧 default 提供），但旧库未同步，导致模型与库长期不一致，
每次 autogenerate 都会产出无意义的 modify_nullable / modify_default 变更。

处理策略：
1. 已验证这 12 列在现有数据中 NULL 计数均为 0，可安全收紧为 NOT NULL；
2. server_default 同步移除，默认值继续由 ORM 的 Python 侧 default 保证（与模型定义一致）；
3. SQLite 不支持 ALTER COLUMN，全部走 batch_alter_table 重建表；重建会连带丢弃该表上的
   27 条业务索引，故每张表重建后立刻重建其业务索引（if_not_exists=True 幂等）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "924992ded229"
down_revision: Union[str, Sequence[str], None] = "cae9dcf72c38"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 受本次重建影响、需要重建业务索引的表（名称/列均取自 app/db/indexes.py）
BUSINESS_INDEXES: dict[str, list[tuple[str, list[str]]]] = {
    "agent_task": [
        ("ix_agent_task_user_status", ["user_id", "status"]),
        ("ix_agent_task_status_ctime", ["status", "create_time"]),
    ],
    "document": [
        ("ix_document_dept_del_ctime", ["dept_id", "is_deleted", "create_time"]),
        ("ix_document_dept_status", ["dept_id", "status", "is_deleted"]),
        ("ix_document_dept_kg_status", ["dept_id", "kg_status"]),
        ("ix_document_parent", ["parent_doc_id"]),
        ("ix_document_dept_hash", ["dept_id", "file_hash"]),
    ],
    "user_notification": [
        ("ix_user_notification_user_read", ["user_id", "read", "create_time"]),
    ],
}

# 目标状态：列名 -> (类型, 升级后 nullable, 升级后 server_default, 回滚时 server_default SQL)
COLUMNS: dict[str, list[tuple[str, sa.types.TypeEngine, str | None]]] = {
    "agent_task": [
        ("schedule_type", sa.String(length=16), "'once'"),
        ("notify_on_finish", sa.Boolean(), "1"),
        ("notified", sa.Boolean(), "0"),
    ],
    "department": [
        ("sort_order", sa.Integer(), "0"),
    ],
    "document": [
        ("kg_status", sa.String(length=16), "'none'"),
        ("kg_entity_count", sa.Integer(), "0"),
        ("kg_relation_count", sa.Integer(), "0"),
        ("view_count", sa.Integer(), "0"),
        ("retrieve_count", sa.Integer(), "0"),
    ],
    "user": [
        ("totp_enabled", sa.Boolean(), "0"),
        ("login_fail_count", sa.Integer(), "0"),
    ],
    "user_notification": [
        ("category", sa.String(length=32), "'system'"),
    ],
}


def _restore_indexes(table: str) -> None:
    for name, cols in BUSINESS_INDEXES.get(table, []):
        op.create_index(name, table, cols, unique=False, if_not_exists=True)


def _alter(table: str, nullable: bool, keep_default: bool) -> None:
    """batch 重建一张表：nullable 统一设置；keep_default=True 时保留原 server_default（回滚用）。"""
    with op.batch_alter_table(table) as batch_op:
        for name, type_, ddl in COLUMNS[table]:
            batch_op.alter_column(
                name,
                existing_type=type_,
                nullable=nullable,
                server_default=sa.text(ddl) if keep_default else None,
            )
    _restore_indexes(table)


def upgrade() -> None:
    """收紧为 NOT NULL 并移除 server_default，使库结构与当前模型一致。"""
    for table in COLUMNS:
        _alter(table, nullable=False, keep_default=False)


def downgrade() -> None:
    """回滚：恢复 nullable=True 与历史 server_default。"""
    for table in COLUMNS:
        _alter(table, nullable=True, keep_default=True)
