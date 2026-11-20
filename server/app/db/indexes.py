# -*- coding: utf-8 -*-
"""P1-2 修复：高频查询列索引补齐（幂等）。

背景：原库仅有 13 个索引（且业务表几乎全裸），document / doc_chunk / operation_log /
conversation / agent_task 等高频表的过滤列（dept_id、is_deleted、create_time、doc_id、
status）均无索引，导致列表分页、审计查询、切片加载全部退化为全表扫描，数据量上来后
接口耗时随行数线性增长。

实现要点：
1. 全部使用 CREATE INDEX IF NOT EXISTS，可重复执行（启动钩子每次跑也无副作用）。
2. 执行前用 inspector 校验表与列是否存在，缺表/缺列（旧库未迁移）则跳过并告警，
   避免因单条 DDL 失败阻断启动。
3. 索引名统一 ix_ 前缀 + 表名 + 列组合，便于 sqlite_master 核查与后续删除。
"""
import logging

from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)

# (索引名, 表名, 列表达式) —— 列表达式支持复合索引，直接拼进 DDL
INDEX_DEFINITIONS: list[tuple[str, str, str]] = [
    # 文档列表/回收站：dept_id + is_deleted 过滤，create_time 排序
    ("ix_document_dept_del_ctime", "document", "dept_id, is_deleted, create_time"),
    ("ix_document_dept_status", "document", "dept_id, status, is_deleted"),
    ("ix_document_dept_kg_status", "document", "dept_id, kg_status"),
    ("ix_document_parent", "document", "parent_doc_id"),
    ("ix_document_dept_hash", "document", "dept_id, file_hash"),
    # 切片按文档加载/删除
    ("ix_doc_chunk_doc", "doc_chunk", "doc_id, chunk_index"),
    ("ix_doc_chunk_chroma", "doc_chunk", "chroma_id"),
    # 审计日志按时间倒序分页、按用户/动作筛选
    ("ix_operation_log_create_time", "operation_log", "create_time"),
    ("ix_operation_log_user_ctime", "operation_log", "user_id, create_time"),
    ("ix_operation_log_action_ctime", "operation_log", "action, create_time"),
    # 会话列表按用户更新时间倒序
    ("ix_conversation_user_utime", "conversation", "user_id, update_time"),
    ("ix_conversation_update_time", "conversation", "update_time"),
    # 会话消息按会话拉取
    ("ix_conversation_msg_conv", "conversation_msg", "conv_id, id"),
    ("ix_conversation_msg_conv_time", "conversation_msg", "conv_id, create_time"),
    # Agent 任务按用户/状态轮询
    ("ix_agent_task_user_status", "agent_task", "user_id, status"),
    ("ix_agent_task_status_ctime", "agent_task", "status, create_time"),
    # 知识图谱按文档清理与按名称查实体
    ("ix_entity_doc", "entity", "doc_id"),
    ("ix_entity_name", "entity", "entity_name"),
    ("ix_entity_relation_doc", "entity_relation", "doc_id"),
    ("ix_entity_relation_source", "entity_relation", "source_entity_id"),
    ("ix_entity_relation_target", "entity_relation", "target_entity_id"),
    # 标签关联（按文档/按标签双向查）
    ("ix_doc_tag_rel_doc", "doc_tag_rel", "doc_id"),
    ("ix_doc_tag_rel_tag", "doc_tag_rel", "tag_id"),
    # 下载审批按文档与状态
    ("ix_download_approval_doc", "download_approval", "doc_id"),
    ("ix_download_approval_status", "download_approval", "status, apply_time"),
    # 站内信未读红点
    ("ix_user_notification_user_read", "user_notification", "user_id, read, create_time"),
    # 安全事件时间线
    ("ix_security_event_user_ctime", "security_event", "user_id, create_time"),
]


def ensure_indexes(engine) -> list[str]:
    """幂等补齐索引，返回本次新创建的索引名列表。"""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    created: list[str] = []
    for name, table, columns in INDEX_DEFINITIONS:
        if table not in tables:
            logger.debug("跳过索引 %s：表 %s 不存在", name, table)
            continue
        existing_cols = {c["name"] for c in inspector.get_columns(table)}
        needed = [c.strip() for c in columns.split(",")]
        missing = [c for c in needed if c not in existing_cols]
        if missing:
            logger.warning("跳过索引 %s：表 %s 缺少列 %s", name, table, missing)
            continue
        with engine.begin() as conn:
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})"))
        created.append(name)
    if created:
        logger.info("索引补齐完成，共 %d 条：%s", len(created), ", ".join(created))
    return created


def list_indexes(engine) -> list[str]:
    """列出当前库内业务索引名（供验证脚本使用）。"""
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'ix_%' ORDER BY name")
        ).fetchall()
    return [r[0] for r in rows]
