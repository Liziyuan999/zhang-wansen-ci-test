# -*- coding: utf-8 -*-
"""一次性孤儿数据清理脚本（阶段二批次1 · P1-3）。

背景：P1-3 修复前，文档永久删除只删了 document 行、向量与物理文件，
doc_chunk / entity / entity_relation / doc_tag_rel / download_approval 均残留，
形成"文档已不存在但关联行还在"的孤儿数据（实测孤儿切片 doc_id=45）。

本脚本按"关系库为准"的方向做一次全量体检与清理：
1. 关系库孤儿行：关联表 doc_id 在 document 表中不存在 -> 物理删除；
2. 向量库孤儿向量：向量 metadata.doc_id 在 document 中不存在，或其向量 id
   不在 doc_chunk.chroma_id 集合内 -> 从 Chroma / 内存中物理删除；
3. 输出每类清理条数，可重复执行（幂等，第二次运行应全部为 0）。

用法（在 server 目录下执行，确保 Chroma 相对路径 ./chroma_data 一致）：
    python scripts/clean_orphans.py            # 仅体检，打印将清理的数量
    python scripts/clean_orphans.py --apply    # 真正执行删除
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402

from app.models import Base as ModelBase  # noqa: F401,E402  确保模型注册后再建表
from app.db.session import SessionLocal, engine  # noqa: E402
from app.services.vector_store import VectorStoreRepository  # noqa: E402

# 确保补偿表 vector_orphan 等新表已建（幂等）
ModelBase.metadata.create_all(bind=engine)

# (表名, 外键列, 说明) —— 关联表按此顺序清理，避免外键悬空
RELATED_TABLES = [
    ("entity_relation", "doc_id", "实体关系"),
    ("entity", "doc_id", "实体"),
    ("doc_chunk", "doc_id", "文档切片"),
    ("doc_tag_rel", "doc_id", "文档标签关联"),
    ("download_approval", "doc_id", "下载审批"),
]


def _scalar(db, sql: str, **params):
    return db.execute(text(sql), params).scalar() or 0


def main() -> int:
    parser = argparse.ArgumentParser(description="清理文档永久删除后遗留的孤儿数据")
    parser.add_argument("--apply", action="store_true", help="真正执行删除（默认仅体检）")
    args = parser.parse_args()

    db = SessionLocal()
    report: list[str] = []
    total = 0
    try:
        alive = _scalar(db, "SELECT COUNT(*) FROM document")
        report.append(f"当前文档数: {alive}")

        # ---------- 1. 关系库孤儿行 ----------
        for table, col, label in RELATED_TABLES:
            cnt = _scalar(
                db,
                f"SELECT COUNT(*) FROM {table} WHERE {col} NOT IN (SELECT id FROM document)",
            )
            if cnt and args.apply:
                db.execute(
                    text(f"DELETE FROM {table} WHERE {col} NOT IN (SELECT id FROM document)")
                )
                db.commit()
            total += cnt
            report.append(f"{label}（{table}）孤儿行: {cnt}{'，已清理' if cnt and args.apply else ''}")

        orphan_doc_ids = [
            r[0]
            for r in db.execute(
                text("SELECT DISTINCT doc_id FROM doc_chunk WHERE doc_id NOT IN (SELECT id FROM document)")
            ).all()
        ]
        if orphan_doc_ids:
            report.append(f"孤儿切片涉及的 doc_id: {sorted(orphan_doc_ids)}")

        # ---------- 2. 向量库孤儿向量 ----------
        valid_doc_ids = {r[0] for r in db.execute(text("SELECT id FROM document")).all()}
        valid_chunk_ids = {
            str(r[0]) for r in db.execute(text("SELECT chroma_id FROM doc_chunk WHERE chroma_id IS NOT NULL")).all()
        }
        store = VectorStoreRepository()
        ids, doc_ids = store.list_all_ids()
        stray = [
            (cid, did)
            for cid, did in zip(ids, doc_ids)
            if did not in valid_doc_ids or str(cid) not in valid_chunk_ids
        ]
        if args.apply and stray:
            store.purge_orphans(valid_doc_ids, valid_chunk_ids)
        total += len(stray)
        report.append(f"向量库向量总数: {len(ids)}，孤儿向量: {len(stray)}{'，已清理' if stray and args.apply else ''}")
        for cid, did in stray[:20]:
            report.append(f"  - 孤儿向量 id={cid} doc_id={did}")

        # ---------- 3. 补偿队列现状（不清理，由启动钩子重放） ----------
        pending = _scalar(db, "SELECT COUNT(*) FROM vector_orphan")
        report.append(f"待补偿向量清理任务（vector_orphan）: {pending}")
    finally:
        db.close()

    print("\n".join(report))
    print(f"\n{'已执行清理' if args.apply else '仅体检（加 --apply 执行）'}，命中总计: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
