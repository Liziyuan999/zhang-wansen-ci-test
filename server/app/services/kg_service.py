# -*- coding: utf-8 -*-
"""知识图谱服务（GraphRAG）：实体/关系抽取（LLM + 规则降级）与图谱查询。

抽取流程：
  1. 优先 LLM（默认 deepseek-chat）从 doc_chunk 批量抽取实体与关系；
  2. LLM 失败 / 未配置时自动降级为规则抽取（技术名词/专有名词正则 + 同切片共现关系）；
  3. 抽取状态与统计写回 document（kg_status / kg_entity_count / kg_relation_count）。
"""
import json
import logging
import re
from collections import defaultdict
from datetime import datetime

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.core.code import NOT_FOUND
from app.core.response import BizError
from app.models import DocChunk, Document, Entity, EntityRelation
from app.services.llm import chat_completion

logger = logging.getLogger(__name__)

EXTRACT_BATCH = 20          # 每批抽取的切片数
MAX_ENTITIES_PER_BATCH = 30
MAX_RELATIONS_PER_BATCH = 50

# 规则抽取：英文技术名词 / 中文专有名词
EN_WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9._+-]{1,28}\b")
CN_TERM_RE = re.compile(r"[\u4e00-\u9fff]{2,6}")
JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)

STOP_WORDS = {
    "the", "and", "for", "with", "from", "this", "that", "are", "was", "were",
    "has", "have", "will", "not", "you", "your", "our", "their", "they", "can",
    "all", "any", "but", "into", "them", "these", "those", "which", "where",
    "when", "what", "who", "how", "why", "about", "after", "before", "during",
    "through", "under", "over", "between", "being", "been", "its", "also",
    "more", "most", "such", "each", "other", "some", "than", "then", "there",
    "please", "based", "according", "知识", "内容", "系统", "文档", "文件", "以下",
    "可以", "需要", "进行", "使用", "提供", "包括", "以及", "相关", "通过", "实现",
    "企业", "工作", "部门", "用户", "信息", "数据", "分析", "管理", "支持",
}


def _clean_name(name: str) -> str:
    name = re.sub(r"\s+", " ", str(name or "")).strip()
    name = name.strip("·。.;;，,、\"'“”‘’《》【】()（）[]{}<>")
    if len(name) < 2 or len(name) > 64:
        return ""
    return name


def _extract_json(text: str) -> dict | None:
    """从 LLM 输出提取 JSON（支持 ```json 包裹）。"""
    raw = text.strip()
    m = JSON_BLOCK_RE.search(raw)
    if m:
        raw = m.group(1).strip()
    try:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            return json.loads(raw[start : end + 1])
    except Exception:  # noqa: BLE001
        return None
    return None


def _llm_extract(db: Session, user_id: int, chunks_text: str, provider_id: int | None = None) -> tuple[list[dict], list[dict]]:
    # ===== 逐行注释：LLM 实体/关系抽取（首选通道）=====
    # 1. 构造抽取 Prompt：要求模型按 JSON 输出实体（name/type/description）与关系（source/target/type），
    #    并通过"宁缺毋滥""保持原文表述"等约束提高抽取质量；文本截断到 6000 字符控制 token 成本。
    # 2. chat_completion() 是 LLM 统一调用封装：传入用户 ID 用于计费统计（scenario=kg_extract）、
    #    temperature=0.3 降低随机性、max_tokens=2000 防止超长输出、provider_id 指定模型供应商。
    # 3. _extract_json() 负责从模型输出中稳健解析 JSON（容忍 ```json 代码块包裹）。
    # 4. 清洗与去重：实体名经 _clean_name 规范化（压缩空白、去掉标点、限制长度 2-64）；
    #    关系要求 source/target 必须是已抽取实体，且去重（seen_rel 集合），避免脏数据。
    """调用 LLM 抽取实体与关系；失败抛异常由上层降级。"""
    prompt = (
        "你是企业知识图谱构建器。请从下面的文本片段中抽取核心实体（人物/组织/产品/技术/地点/事件/其他）"
        "以及实体之间的语义关系。\n"
        "抽取要求：1) 实体名称保持原文表述；2) 每个实体给出类型与一句话描述；"
        "3) 关系只保留明确可依据原文的关系（如 研发/使用/包含/负责/位于/合作/发布 等），"
        "source 与 target 必须是已抽取的实体名；4) 宁缺毋滥，不抽取无意义碎片。\n"
        "严格输出 JSON，不要输出其他内容：\n"
        '{"entities":[{"name":"实体名","type":"person|org|product|tech|place|event|other","description":"描述"}],'
        '"relations":[{"source":"实体A","target":"实体B","type":"关系类型"}]}\n\n'
        "文本片段：\n" + chunks_text[:6000]
    )
    raw = chat_completion(
        db, user_id,
        [{"role": "user", "content": prompt}],
        scenario="kg_extract",
        temperature=0.3,
        max_tokens=2000,
        provider_id=provider_id,
    )
    parsed = _extract_json(raw) or {}
    entities: list[dict] = []
    seen_names: set[str] = set()
    for e in (parsed.get("entities") or [])[: MAX_ENTITIES_PER_BATCH]:
        name = _clean_name(e.get("name"))
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        entities.append(
            {
                "name": name,
                "type": str(e.get("type") or "other")[:32],
                "description": str(e.get("description") or "")[:300],
            }
        )
    relations: list[dict] = []
    seen_rel: set[tuple[str, str, str]] = set()
    for r in (parsed.get("relations") or [])[: MAX_RELATIONS_PER_BATCH]:
        src = _clean_name(r.get("source"))
        tgt = _clean_name(r.get("target"))
        rtype = str(r.get("type") or "相关").strip()[:32] or "相关"
        if not src or not tgt or src == tgt or (src, tgt, rtype) in seen_rel:
            continue
        if src not in seen_names or tgt not in seen_names:
            continue
        seen_rel.add((src, tgt, rtype))
        relations.append({"source": src, "target": tgt, "type": rtype})
    return entities, relations


def _rule_extract_chunk(text: str) -> tuple[list[str], list[tuple[str, str]]]:
    """规则降级抽取：英文技术名词 + 中文专有名词；同切片共现关系。"""
    entities: list[str] = []
    seen: set[str] = set()
    for m in EN_WORD_RE.finditer(text):
        w = m.group(0)
        if w.lower() in STOP_WORDS or len(w) < 2:
            continue
        if w.lower() not in seen:
            seen.add(w.lower())
            entities.append(w)
    for m in CN_TERM_RE.finditer(text):
        w = m.group(0)
        if w in STOP_WORDS or w in seen:
            continue
        seen.add(w)
        entities.append(w)
    entities = entities[:8]
    relations: list[tuple[str, str]] = []
    n = len(entities)
    for i in range(n):
        for j in range(i + 1, n):
            relations.append((entities[i], entities[j]))
            if len(relations) >= 10:
                return entities, relations
    return entities, relations


def extract_document_kg(
    db: Session, user, doc_id: int, provider_id: int | None = None
) -> dict:
    """对文档执行实体/关系抽取（幂等：先清空旧数据再写入），返回抽取统计。"""
    doc = db.get(Document, doc_id)
    if not doc or doc.is_deleted:
        raise BizError(NOT_FOUND, "文档不存在")
    if doc.dept_id != user.dept_id:
        raise BizError(NOT_FOUND, "文档不存在或不可访问")

    chunks = (
        db.query(DocChunk)
        .filter(DocChunk.doc_id == doc_id)
        .order_by(DocChunk.id.asc())
        .all()
    )
    if not chunks:
        raise BizError(NOT_FOUND, "文档尚未解析出切片，无法抽取")

    # 幂等：清空该文档已有图谱数据
    old_entities = db.query(Entity).filter(Entity.doc_id == doc_id).all()
    old_ids = [e.id for e in old_entities]
    if old_ids:
        db.query(EntityRelation).filter(EntityRelation.source_entity_id.in_(old_ids)).delete(synchronize_session=False)
        db.query(EntityRelation).filter(EntityRelation.target_entity_id.in_(old_ids)).delete(synchronize_session=False)
    db.query(Entity).filter(Entity.doc_id == doc_id).delete(synchronize_session=False)
    db.query(EntityRelation).filter(EntityRelation.doc_id == doc_id).delete(synchronize_session=False)

    doc.kg_status = "processing"
    db.commit()

    entity_rows: list[Entity] = []
    relation_rows: list[EntityRelation] = []
    used_llm = False
    err_msg: str | None = None
    # 跨批次去重：同一文档内实体名唯一（entity_name+doc_id 唯一约束）
    name_to_id: dict[str, int] = {}

    try:
        for start in range(0, len(chunks), EXTRACT_BATCH):
            batch = chunks[start : start + EXTRACT_BATCH]
            batch_text = "\n\n".join(f"[切片{idx + 1}] {c.chunk_text}" for idx, c in enumerate(batch))
            llm_ok = False
            try:
                ents, rels = _llm_extract(db, user.id, batch_text, provider_id)
                llm_ok = True
            except Exception as exc:  # noqa: BLE001
                logger.warning("LLM 抽取失败（doc=%s），降级规则抽取: %s", doc_id, exc)
                err_msg = f"LLM 抽取失败，已降级规则抽取：{str(exc)[:120]}"
                ents, rels = [], []

            # 规则补充/降级：LLM 未产出时用规则，LLM 产出时用规则补齐英文技术名词
            rule_ents: set[str] = set()
            rule_rels: list[tuple[str, str]] = []
            if not llm_ok or len(ents) < 3:
                for c in batch:
                    re_ents, re_rels = _rule_extract_chunk(c.chunk_text)
                    rule_ents.update(re_ents)
                    rule_rels.extend(re_rels)
                if not llm_ok:
                    ents = [{"name": n, "type": "tech", "description": "规则抽取（LLM 不可用）"} for n in rule_ents]
                    rels = [{"source": s, "target": t, "type": "共现"} for s, t in rule_rels]

            for e in ents:
                name = e["name"]
                if name in name_to_id:
                    continue
                row = Entity(
                    entity_name=name,
                    entity_type=e.get("type") or "other",
                    description=e.get("description") or "",
                    doc_id=doc_id,
                    chunk_id=batch[0].chroma_id,
                    source="llm" if llm_ok else "rule",
                )
                db.add(row)
                db.flush()
                name_to_id[name] = row.id
                entity_rows.append(row)
            for r in rels:
                src_id = name_to_id.get(r["source"])
                tgt_id = name_to_id.get(r["target"])
                if not src_id or not tgt_id:
                    continue
                rel = EntityRelation(
                    source_entity_id=src_id,
                    target_entity_id=tgt_id,
                    relation_type=r["type"],
                    doc_id=doc_id,
                    chunk_id=batch[0].chroma_id,
                    source="llm" if llm_ok else "rule",
                )
                db.add(rel)
                relation_rows.append(rel)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        doc.kg_status = "failed"
        doc.kg_error = str(exc)[:300]
        db.commit()
        logger.exception("知识图谱抽取失败 doc=%s", doc_id)
        raise BizError(NOT_FOUND, f"知识图谱抽取失败：{exc}") from exc

    doc.kg_status = "success" if entity_rows else "failed"
    doc.kg_entity_count = len(entity_rows)
    doc.kg_relation_count = len(relation_rows)
    doc.kg_error = err_msg if entity_rows and err_msg else (None if entity_rows else "未抽取到实体")
    doc.kg_finish_time = datetime.now()
    db.commit()
    return {
        "doc_id": doc_id,
        "entities": len(entity_rows),
        "relations": len(relation_rows),
        "source": "llm" if used_llm or any(r.source == "llm" for r in entity_rows) else "rule",
        "error": doc.kg_error,
    }


def _visible_doc_ids(db: Session, user) -> list[int]:
    """当前用户可见文档 ID 集合（部门隔离），与文档接口口径保持一致。"""
    rows = (
        db.query(Document.id)
        .filter(Document.dept_id == user.dept_id, Document.is_deleted == False)  # noqa: E712
        .all()
    )
    return [r[0] for r in rows]


def get_graph(db: Session, user, doc_id: int | None = None, keyword: str | None = None, limit: int = 200) -> dict:
    """返回图谱数据：nodes（含度数便于前端布局）+ links。支持按文档/关键词过滤。

    部门隔离：仅在当前用户部门可见文档范围内返回实体与关系，避免跨部门数据泄漏。
    """
    visible = _visible_doc_ids(db, user)
    if not visible:
        return {"nodes": [], "links": []}
    q = db.query(Entity)
    if doc_id is not None:
        if doc_id not in set(visible):
            raise BizError(NOT_FOUND, "文档不存在或不可访问")
        q = q.filter(Entity.doc_id == doc_id)
    else:
        q = q.filter(Entity.doc_id.in_(visible))
    if keyword:
        q = q.filter(Entity.entity_name.contains(keyword))
    entities = q.order_by(Entity.id.asc()).limit(limit).all()
    if not entities:
        return {"nodes": [], "links": []}
    eids = [e.id for e in entities]
    rels = (
        db.query(EntityRelation)
        .filter(EntityRelation.source_entity_id.in_(eids), EntityRelation.target_entity_id.in_(eids))
        .all()
    )
    id_to_entity = {e.id: e for e in entities}
    degree: dict[int, int] = defaultdict(int)
    links = []
    for r in rels:
        if r.source_entity_id not in id_to_entity or r.target_entity_id not in id_to_entity:
            continue
        degree[r.source_entity_id] += 1
        degree[r.target_entity_id] += 1
        links.append(
            {
                "source": r.source_entity_id,
                "target": r.target_entity_id,
                "relation_type": r.relation_type,
                "doc_id": r.doc_id,
            }
        )
    nodes = []
    for e in entities:
        nodes.append(
            {
                "id": e.id,
                "name": e.entity_name,
                "type": e.entity_type,
                "description": e.description or "",
                "doc_id": e.doc_id,
                "degree": degree.get(e.id, 0),
                "source": e.source,
            }
        )
    return {"nodes": nodes, "links": links}


def search_entities(db: Session, user, keyword: str, limit: int = 20) -> list[dict]:
    """实体搜索：按名称模糊匹配，返回实体 + 关联文档 + 关系条数（限当前用户部门可见范围）。"""
    visible = _visible_doc_ids(db, user)
    if not visible:
        return []
    q = (
        db.query(Entity)
        .filter(
            Entity.doc_id.in_(visible),
            Entity.entity_name.contains(keyword),
        )
        .order_by(Entity.id.desc())
        .limit(limit)
        .all()
    )
    out = []
    # P1-7：原实现为每个实体单独 count 关系数（N+1），改为一次 IN 查询后内存计数
    ent_ids = [e.id for e in q]
    rel_count_map: dict[int, int] = {}
    if ent_ids:
        ent_set = set(ent_ids)
        rel_rows = (
            db.query(EntityRelation.source_entity_id, EntityRelation.target_entity_id)
            .filter(
                (EntityRelation.source_entity_id.in_(ent_ids)) | (EntityRelation.target_entity_id.in_(ent_ids))
            )
            .all()
        )
        for sid, tid in rel_rows:
            # 自环关系只计一次，保持与原 count() 语义一致
            for eid in {sid, tid}:
                if eid in ent_set:
                    rel_count_map[eid] = rel_count_map.get(eid, 0) + 1
    for e in q:
        rel_count = rel_count_map.get(e.id, 0)
        out.append(
            {
                "id": e.id,
                "name": e.entity_name,
                "type": e.entity_type,
                "description": e.description or "",
                "doc_id": e.doc_id,
                "relation_count": rel_count,
                "source": e.source,
            }
        )
    return out


def get_stats(db: Session, user) -> dict:
    """图谱统计：实体数 / 关系数 / 已抽取文档数 / 实体类型分布（限当前用户部门可见范围）。"""
    visible = _visible_doc_ids(db, user)
    if visible:
        entity_count = db.query(Entity).filter(Entity.doc_id.in_(visible)).count()
        relation_count = db.query(EntityRelation).filter(EntityRelation.doc_id.in_(visible)).count()
        type_rows = (
            db.query(Entity.entity_type, sa_func.count(Entity.id))
            .filter(Entity.doc_id.in_(visible))
            .group_by(Entity.entity_type)
            .all()
        )
    else:
        entity_count = 0
        relation_count = 0
        type_rows = []
    doc_count = (
        db.query(Document)
        .filter(
            Document.kg_status == "success",
            Document.dept_id == user.dept_id,
            Document.is_deleted == False,  # noqa: E712
        )
        .count()
    )
    return {
        "entity_count": entity_count,
        "relation_count": relation_count,
        "doc_count": doc_count,
        "type_distribution": [{"type": t, "count": c} for t, c in type_rows],
    }
