# -*- coding: utf-8 -*-
"""轻量 SQLite 列迁移：为已存在的表补充新增字段（幂等）。

create_all 只会创建新表、不会为已有表加列，因此需要此补丁。
每列尝试 ALTER TABLE ADD COLUMN，若列已存在则跳过。
"""
import logging

from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)


def apply_column_patches(engine) -> None:
    """按 (表名, 列名, DDL) 列表逐个补齐缺失列。"""
    inspector = inspect(engine)
    existing = {}
    for table_name in inspector.get_table_names():
        existing[table_name] = {col["name"] for col in inspector.get_columns(table_name)}

    patches = [
        ("user", "avatar", "ALTER TABLE user ADD COLUMN avatar VARCHAR(255)"),
        ("user", "totp_secret", "ALTER TABLE user ADD COLUMN totp_secret VARCHAR(64)"),
        ("user", "totp_enabled", "ALTER TABLE user ADD COLUMN totp_enabled BOOLEAN DEFAULT 0"),
        ("user", "login_fail_count", "ALTER TABLE user ADD COLUMN login_fail_count INTEGER DEFAULT 0"),
        ("user", "login_locked_until", "ALTER TABLE user ADD COLUMN login_locked_until DATETIME"),
        ("agent_task", "template_id", "ALTER TABLE agent_task ADD COLUMN template_id INTEGER"),
        ("agent_task", "schedule_type", "ALTER TABLE agent_task ADD COLUMN schedule_type VARCHAR(16) DEFAULT 'once'"),
        ("agent_task", "schedule_cron", "ALTER TABLE agent_task ADD COLUMN schedule_cron VARCHAR(64)"),
        ("agent_task", "notify_on_finish", "ALTER TABLE agent_task ADD COLUMN notify_on_finish BOOLEAN DEFAULT 1"),
        ("agent_task", "notified", "ALTER TABLE agent_task ADD COLUMN notified BOOLEAN DEFAULT 0"),
        ("team", "parent_id", "ALTER TABLE team ADD COLUMN parent_id INTEGER"),
        ("team_member", "perms", "ALTER TABLE team_member ADD COLUMN perms JSON"),
        ("department", "parent_id", "ALTER TABLE department ADD COLUMN parent_id INTEGER"),
        ("department", "leader_id", "ALTER TABLE department ADD COLUMN leader_id INTEGER"),
        ("department", "description", "ALTER TABLE department ADD COLUMN description VARCHAR(255)"),
        ("department", "sort_order", "ALTER TABLE department ADD COLUMN sort_order INTEGER DEFAULT 0"),
        ("user_notification", "category", "ALTER TABLE user_notification ADD COLUMN category VARCHAR(32) DEFAULT 'system'"),
        # 企业打卡四段班次 + 定位审计（旧表补充列）
        ("attendance_record", "am_out_time", "ALTER TABLE attendance_record ADD COLUMN am_out_time DATETIME"),
        ("attendance_record", "pm_in_time", "ALTER TABLE attendance_record ADD COLUMN pm_in_time DATETIME"),
        ("attendance_record", "pm_out_time", "ALTER TABLE attendance_record ADD COLUMN pm_out_time DATETIME"),
        ("attendance_record", "checkin_meta", "ALTER TABLE attendance_record ADD COLUMN checkin_meta TEXT"),
        # 审批超时催办标记（防重复催办）
        ("download_approval", "reminder_sent_at", "ALTER TABLE download_approval ADD COLUMN reminder_sent_at DATETIME"),
        ("team_exit_approval", "reminder_sent_at", "ALTER TABLE team_exit_approval ADD COLUMN reminder_sent_at DATETIME"),
        ("attendance_fix_approval", "reminder_sent_at", "ALTER TABLE attendance_fix_approval ADD COLUMN reminder_sent_at DATETIME"),
        # 知识图谱（GraphRAG）：文档抽取状态与统计
        ("document", "kg_status", "ALTER TABLE document ADD COLUMN kg_status VARCHAR(16) DEFAULT 'none'"),
        ("document", "kg_entity_count", "ALTER TABLE document ADD COLUMN kg_entity_count INTEGER DEFAULT 0"),
        ("document", "kg_relation_count", "ALTER TABLE document ADD COLUMN kg_relation_count INTEGER DEFAULT 0"),
        ("document", "kg_error", "ALTER TABLE document ADD COLUMN kg_error VARCHAR(300)"),
        ("document", "kg_finish_time", "ALTER TABLE document ADD COLUMN kg_finish_time DATETIME"),
        # 文档热度（智能看板）：浏览量 + 检索命中
        ("document", "view_count", "ALTER TABLE document ADD COLUMN view_count INTEGER DEFAULT 0"),
        ("document", "retrieve_count", "ALTER TABLE document ADD COLUMN retrieve_count INTEGER DEFAULT 0"),
        # Agent 拖拽式工作流编排：模板/任务画布 JSON
        ("agent_template", "canvas_json", "ALTER TABLE agent_template ADD COLUMN canvas_json TEXT"),
        ("agent_task", "canvas_json", "ALTER TABLE agent_task ADD COLUMN canvas_json TEXT"),
    ]

    with engine.begin() as conn:
        for table_name, col_name, ddl in patches:
            cols = existing.get(table_name, set())
            if col_name in cols:
                continue
            try:
                conn.execute(text(ddl))
                logger.info("迁移成功：%s 表新增列 %s", table_name, col_name)
            except Exception as exc:  # pragma: no cover
                logger.warning("迁移跳过：%s.%s -> %s", table_name, col_name, exc)
