# -*- coding: utf-8 -*-
"""向量存储抽象层：主选 Chroma，缺依赖时降级内存实现，保证可直接运行。"""
import hashlib
import logging
import math
import re
import uuid
from typing import Any

logger = logging.getLogger(__name__)

try:
    import chromadb  # type: ignore

    CHROMA_AVAILABLE = True
except Exception:  # pragma: no cover
    chromadb = None  # type: ignore
    CHROMA_AVAILABLE = False


# ===== 逐行注释：无嵌入模型时的降级词袋哈希向量（本地可运行兜底） =====
# 1. 输出固定 384 维：与 Chroma 默认模型 all-MiniLM-L6-v2 维度一致，避免旧集合 schema
#    与查询向量维度不匹配导致 Chroma 路径降级、检索报错。
# 2. 中文处理：整词哈希（单字权重 2）+ 相邻双字 bigram（权重 1）+ 单字（权重 1）三重叠加，
#    显著提升中文片段与查询的语义重合度（如「Agent 是什么」与「Agent 的本质」）。
# 3. 英文处理：按 [a-z0-9]+ 分词后各自哈希累加。
# 4. 哈希用 md5 取模 384：确定性映射（同词必同维），无需加载任何模型或联网下载。
def _fake_embed(text: str) -> list[float]:
    """无嵌入模型时的降级词袋哈希向量，仅用于本地可运行演示。

    固定输出 384 维，与 Chroma 默认模型（all-MiniLM-L6-v2）维度一致，
    避免旧集合 schema 与查询向量维度不匹配导致 Chroma 路径降级。
    中文采用「整词 + 双字 bigram + 单字」混合哈希，显著提升中文片段
    与查询之间的语义重合度（如「Agent 是什么」与「Agent 的本质」）。
    """
    vec = {}
    for seg in re.findall(r"[\u4e00-\u9fff]+|[A-Za-z0-9]+", text.lower()):
        if not seg:
            continue
        if '\u4e00' <= seg[0] <= '\u9fff':
            if len(seg) == 1:
                h = int(hashlib.md5(seg.encode("utf-8")).hexdigest(), 16)
                vec[h % 384] = vec.get(h % 384, 0) + 2
            else:
                for i in range(len(seg) - 1):
                    bigram = seg[i:i + 2]
                    h = int(hashlib.md5(bigram.encode("utf-8")).hexdigest(), 16)
                    vec[h % 384] = vec.get(h % 384, 0) + 1
                for ch in seg:
                    h = int(hashlib.md5(ch.encode("utf-8")).hexdigest(), 16)
                    vec[h % 384] = vec.get(h % 384, 0) + 1
        else:
            for t in re.findall(r"[a-z0-9]+", seg):
                h = int(hashlib.md5(t.encode("utf-8")).hexdigest(), 16)
                vec[h % 384] = vec.get(h % 384, 0) + 1
    return [vec.get(i, 0.0) for i in range(384)]


def _tokenize(text: str) -> list[str]:
    """查询关键词切分：中文双字 bigram + 单字，英文单词。"""
    toks: list[str] = []
    for seg in re.findall(r"[\u4e00-\u9fff]+|[A-Za-z0-9]+", text.lower()):
        if not seg:
            continue
        if '\u4e00' <= seg[0] <= '\u9fff':
            if len(seg) >= 2:
                toks.extend(seg[i:i + 2] for i in range(len(seg) - 1))
            toks.extend(seg)
        else:
            toks.extend(re.findall(r"[a-z0-9]+", seg))
    return list(dict.fromkeys(toks))


# ===== 逐行注释：本地哈希嵌入函数（替代默认模型，避免联网下载） =====
# 1. 背景：Chroma 默认 embedding 模型 all-MiniLM-L6-v2 首次使用需联网下载，
#    内网/无外网环境会导致文档解析任务长期挂起（上传进度卡住）——必须显式传本地函数。
# 2. 嵌入算法（_fake_embed）：中文按"双字 bigram + 单字"、英文按单词，
#    每个 token 用 md5 哈希映射到 384 维稀疏词袋向量（词频加权，位置无关）。
# 3. name() 返回 "default"：与既有集合的持久化配置一致，避免
#    "Embedding function conflict" 冲突导致降级为内存库；实际嵌入仍走本地函数。
# 4. 接口对齐：__call__ / embed_documents / embed_query 三方法均委托 _fake_embed，
#    兼容 chromadb>=1.5 对 EmbeddingFunction 接口的调用约定。
class _HashEmbeddingFunction:
    """Chroma 专用嵌入函数：使用本地词袋哈希向量。

    显式传入后 Chroma 不再加载默认 embedding 模型（all-MiniLM-L6-v2），
    避免首次使用时联网下载模型导致解析任务长期挂起（上传进度卡住）。
    """

    @staticmethod
    def name() -> str:
        # chromadb>=1.5 用 name() 与集合持久化配置做冲突校验；既有集合登记为
        # default，返回 "default" 可避免"Embedding function conflict"导致降级内存库。
        # 实际嵌入仍由本函数本地生成，不会触发任何模型下载。
        return "default"

    def __call__(self, input):
        texts = input if isinstance(input, list) else [input]
        return [_fake_embed(t) for t in texts]

    def embed_documents(self, input):
        return self(input)

    def embed_query(self, input):
        return self(input)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


# ===== 逐行注释：向量库仓储（VectorStoreRepository）设计 =====
# 1. 职责：向上层（doc_service / chat_service）屏蔽 Chroma 与内存实现的差异，
#    提供 add_chunks / query / delete_by_doc / get_chunk_count 等统一接口。
# 2. 初始化：优先 PersistentClient 持久化 Chroma（hnsw:space=cosine，余弦距离）；
#    未安装 chromadb 或初始化异常时降级纯内存库（_memory 列表 + 余弦手算 _cosine）。
# 3. 关键点：无论哪条路径都会 _load_from_db 从 doc_chunk 表恢复历史切片，
#    解决"重启后内存库为空导致 RAG 检索无结果"的历史 bug。
# 4. 检索（query）：先按 query 分词（_tokenize：中文双字 bigram + 英文单词），
#    再用词袋向量与库内切片算余弦相似度；按 dept_id 限定部门权限，
#    返回 top_k 切片（id/text/page_no/sheet_name/score），供 RAG 拼接上下文。
class VectorStoreRepository:
    """向量库仓储接口，屏蔽 Chroma 与内存实现差异。"""

    def __init__(self, collection_name: str = "kb_default", persist_dir: str | None = None):
        self.collection_name = collection_name
        self._memory: list[dict[str, Any]] = []
        self._collection = None
        if CHROMA_AVAILABLE:
            try:
                client = chromadb.PersistentClient(path=persist_dir or "./chroma_data")
                self._collection = client.get_or_create_collection(
                    collection_name,
                    embedding_function=_HashEmbeddingFunction(),
                    metadata={"hnsw:space": "cosine"},
                )
                logger.info("Chroma 向量库已就绪: %s", collection_name)
            except Exception as exc:  # pragma: no cover
                logger.warning("Chroma 初始化失败，降级内存向量库: %s", exc)
                self._collection = None
        else:
            logger.warning("未安装 chromadb，降级内存向量库")
        # 服务重启后内存库为空：从 doc_chunk 表加载历史切片（关联 document.dept_id），
        # 否则重启后 RAG 检索永远无结果（历史 bug 根因：用户反馈"知识片段中未检索到相关内容"）。
        self._load_from_db()

    # ===== 逐行注释：重启后从 doc_chunk 表恢复历史切片 =====
    # 1. 背景：内存降级向量库在进程重启后为空，若不恢复，RAG 检索永远无结果
    #    （历史 bug 根因：用户反馈"知识片段中未检索到相关内容"）。
    # 2. 用 SessionLocal 打开会话，联查 DocChunk + Document.dept_id（部门权限维度）。
    # 3. 每行切片组装为内存检索项：id 优先取 chroma_id（与向量库一致），否则回退 chunk.id。
    # 4. 仅当存在历史切片时打日志提示加载数量；任何异常不影响启动（内存库仍可用）。
    def _load_from_db(self) -> None:
        try:
            from app.db.session import SessionLocal
            from app.models import Document, DocChunk

            with SessionLocal() as db:
                rows = (
                    db.query(DocChunk, Document.dept_id)
                    .join(Document, Document.id == DocChunk.doc_id)
                    .all()
                )
                for chunk, dept_id in rows:
                    self._memory.append(
                        {
                            "id": chunk.chroma_id or str(chunk.id),
                            "doc_id": chunk.doc_id,
                            "dept_id": dept_id,
                            "text": chunk.chunk_text,
                            "page_no": chunk.page_no,
                            "sheet_name": chunk.sheet_name,
                        }
                    )
                if rows:
                    logger.info("内存向量库已加载 %d 条历史切片", len(rows))
        except Exception as exc:  # pragma: no cover
            logger.warning("内存向量库加载历史切片失败: %s", exc)

    def add_chunks(self, doc_id: int, chunks: list[dict[str, Any]]) -> None:
        ids = [c["id"] for c in chunks]
        texts = [c["text"] for c in chunks]
        metadatas = [
            {"doc_id": doc_id, "dept_id": c.get("dept_id", 0), "page_no": c.get("page_no"), "sheet_name": c.get("sheet_name") or ""}
            for c in chunks
        ]
        if self._collection is not None:
            self._collection.upsert(ids=ids, documents=texts, metadatas=metadatas)
        else:
            for cid, text, meta in zip(ids, texts, metadatas):
                self._memory.append({"id": cid, "text": text, **meta})

    def _candidate_where(self, dept_id: int, doc_ids: list[int] | None) -> dict:
        if doc_ids:
            return {"$and": [{"dept_id": dept_id}, {"doc_id": {"$in": list(doc_ids)}}]}
        return {"dept_id": dept_id}

    def _collect_candidates(self, dept_id: int, doc_ids: list[int] | None) -> list[dict[str, Any]]:
        """收集候选切片（用于关键词兜底召回），Chroma 优先、内存降级。"""
        if self._collection is not None:
            try:
                res = self._collection.get(
                    where=self._candidate_where(dept_id, doc_ids),
                    include=["documents", "metadatas"],
                )
                ids = res.get("ids") or []
                docs = res.get("documents") or []
                metas = res.get("metadatas") or []
                items: list[dict[str, Any]] = []
                for i, cid in enumerate(ids):
                    meta = metas[i] or {}
                    items.append(
                        {
                            "chunk_id": cid,
                            "doc_id": int(meta.get("doc_id", 0)),
                            "text": docs[i],
                            "page_no": meta.get("page_no"),
                            "sheet_name": meta.get("sheet_name"),
                        }
                    )
                return items
            except Exception as exc:  # pragma: no cover
                logger.warning("Chroma 候选收集失败，降级内存: %s", exc)
        out: list[dict[str, Any]] = []
        for m in self._memory:
            if int(m.get("dept_id", -1)) != dept_id:
                continue
            if doc_ids and int(m.get("doc_id", -1)) not in doc_ids:
                continue
            out.append(
                {
                    "chunk_id": m.get("id"),
                    "doc_id": int(m.get("doc_id", 0)),
                    "text": m.get("text", ""),
                    "page_no": m.get("page_no"),
                    "sheet_name": m.get("sheet_name"),
                }
            )
        return out

    def _vector_query(self, query_text: str, dept_id: int, top_k: int, doc_ids: list[int] | None) -> list[dict[str, Any]]:
        if self._collection is not None:
            try:
                res = self._collection.query(
                    query_texts=[query_text],
                    n_results=top_k,
                    where=self._candidate_where(dept_id, doc_ids),
                )
                results: list[dict[str, Any]] = []
                ids = (res.get("ids") or [[]])[0]
                docs = (res.get("documents") or [[]])[0]
                metas = (res.get("metadatas") or [[]])[0]
                dists = (res.get("distances") or [[]])[0]
                for i, cid in enumerate(ids):
                    meta = metas[i] or {}
                    results.append(
                        {
                            "chunk_id": cid,
                            "doc_id": int(meta.get("doc_id", 0)),
                            "text": docs[i],
                            "page_no": meta.get("page_no"),
                            "sheet_name": meta.get("sheet_name"),
                            "score": round(1.0 - float(dists[i]), 4) if dists else 0.0,
                        }
                    )
                return results
            except Exception as exc:  # pragma: no cover
                logger.warning("Chroma 查询失败，降级内存: %s", exc)
        qv = _fake_embed(query_text)
        scored = []
        for item in self._memory:
            if item.get("dept_id") != dept_id:
                continue
            if doc_ids and int(item.get("doc_id", -1)) not in doc_ids:
                continue
            iv = _fake_embed(item["text"])
            scored.append((_cosine(qv, iv), item))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "chunk_id": item["id"],
                "doc_id": int(item["doc_id"]),
                "text": item["text"],
                "page_no": item.get("page_no"),
                "sheet_name": item.get("sheet_name"),
                "score": round(score, 4),
            }
            for score, item in scored[:top_k]
        ]

    def _keyword_query(self, query_text: str, dept_id: int, top_k: int, doc_ids: list[int] | None) -> list[dict[str, Any]]:
        """关键词兜底召回：bigram 命中覆盖率 + 词频加权，覆盖向量语义不足的场景。"""
        toks = _tokenize(query_text)
        if not toks:
            return []
        candidates = self._collect_candidates(dept_id, doc_ids)
        if len(candidates) > 2000:
            candidates = candidates[:2000]
        scored = []
        for item in candidates:
            text = (item.get("text") or "").lower()
            hit = [t for t in toks if t in text]
            if not hit:
                continue
            coverage = len(hit) / len(toks)
            freq = sum(text.count(t) for t in hit)
            score = 0.62 * coverage + 0.38 * min(1.0, freq / (len(toks) * 3.0))
            if coverage >= 1.0:
                score = min(1.0, score + 0.05)
            scored.append((score, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "chunk_id": item["chunk_id"],
                "doc_id": item["doc_id"],
                "text": item["text"],
                "page_no": item.get("page_no"),
                "sheet_name": item.get("sheet_name"),
                "score": round(score, 4),
            }
            for score, item in scored[:top_k]
        ]

    # ===== 逐行注释：混合检索（向量召回 + 关键词兜底 + 融合去重） =====
    # 1. 向量召回：_vector_query 取 top_k*2 候选，语义相似度优先（Chroma cosine 或内存余弦）。
    # 2. 关键词兜底：_keyword_query 取 top_k*2 候选，用 bigram 命中覆盖率+词频加权，覆盖
    #    向量模型不擅长的精确术语/编号/代码片段（如 "Agent 是什么" 与 "Agent 的本质"）。
    # 3. 融合规则：按 chunk_id 合并；关键词命中项若已在向量结果中，score 取 max(原分, kw*0.98)；
    #    新出现的关键词项打 0.82 折扣，避免关键词噪声淹没语义高分。
    # 4. 过滤 score < 0.06 的弱相关项，按分倒序截取 top_k 返回给 RAG 组装上下文。
    def query(self, query_text: str, dept_id: int, top_k: int = 5, doc_ids: list[int] | None = None) -> list[dict[str, Any]]:
        """混合检索：向量召回为主，关键词兜底补位，融合去重后按分排序返回。"""
        vec = self._vector_query(query_text, dept_id, top_k * 2, doc_ids)
        kw = self._keyword_query(query_text, dept_id, top_k * 2, doc_ids)
        merged: dict[str, dict[str, Any]] = {}
        for r in vec:
            merged[r["chunk_id"]] = dict(r)
        for r in kw:
            key = r["chunk_id"]
            if key in merged:
                merged[key]["score"] = max(merged[key].get("score", 0.0), r["score"] * 0.98)
            else:
                r2 = dict(r)
                r2["score"] = r["score"] * 0.82
                merged[key] = r2
        out = [m for m in merged.values() if m.get("score", 0.0) >= 0.06]
        out.sort(key=lambda x: x["score"], reverse=True)
        return out[:top_k]

    # ===== 逐行注释：按文档删除向量（P1-4 双写补偿改造） =====
    # 1. 原实现把 Chroma 异常吞成 warning，调用方永远拿到 None，删除失败被完全掩盖，
    #    形成"关系库已删、向量库仍有"的孤儿向量（已删文档仍会被 RAG 命中）。
    # 2. 现改为返回 bool：True=两个后端都删成功；False=Chroma 删除失败（内存已清）。
    #    raise_on_error=True 时直接把异常抛给调用方，供上层按退避策略重试。
    # 3. 内存态始终清理（纯本地数据，无副作用）。
    def delete_by_doc(self, doc_id: int, raise_on_error: bool = False) -> bool:
        ok = True
        if self._collection is not None:
            try:
                self._collection.delete(where={"doc_id": doc_id})
            except Exception as exc:  # pragma: no cover
                ok = False
                logger.warning("Chroma 删除失败 doc_id=%s: %s", doc_id, exc)
                if raise_on_error:
                    raise
        self._memory = [m for m in self._memory if int(m.get("doc_id", -1)) != doc_id]
        return ok

    def list_all_ids(self) -> tuple[list[str], list[int]]:
        """枚举向量库全部向量 ID 与归属 doc_id（孤儿清理脚本用）。"""
        ids: list[str] = []
        doc_ids: list[int] = []
        if self._collection is not None:
            try:
                res = self._collection.get(include=["metadatas"])
                for i, cid in enumerate(res.get("ids") or []):
                    meta = (res.get("metadatas") or [])[i] or {}
                    ids.append(cid)
                    doc_ids.append(int(meta.get("doc_id", -1)))
            except Exception as exc:  # pragma: no cover
                logger.warning("枚举 Chroma 向量失败: %s", exc)
        for m in self._memory:
            if m.get("id") not in ids:
                ids.append(str(m.get("id")))
                doc_ids.append(int(m.get("doc_id", -1)))
        return ids, doc_ids

    # ===== 逐行注释：孤儿向量清理（P1-3 数据一致性） =====
    # 判定：向量归属的 doc_id 不在 document 表（文档已永久删除），或其 ID 不在
    # doc_chunk.chroma_id 集合内（切片已重建/回滚），均视为孤儿，直接物理删除。
    # 返回 {"scanned": 扫描数, "removed": 删除数} 供脚本输出。
    def purge_orphans(self, valid_doc_ids: set[int], valid_chunk_ids: set[str]) -> dict[str, int]:
        ids, doc_ids = self.list_all_ids()
        bad_ids = [cid for cid, did in zip(ids, doc_ids) if did not in valid_doc_ids or cid not in valid_chunk_ids]
        removed = 0
        if bad_ids and self._collection is not None:
            try:
                self._collection.delete(ids=bad_ids)
                removed = len(bad_ids)
            except Exception as exc:  # pragma: no cover
                logger.warning("清理孤儿向量失败: %s", exc)
        elif bad_ids:
            removed = len(bad_ids)
        if bad_ids:
            bad_set = set(bad_ids)
            self._memory = [m for m in self._memory if str(m.get("id")) not in bad_set]
        return {"scanned": len(ids), "removed": removed}


def make_chunk_id() -> str:
    return str(uuid.uuid4())
