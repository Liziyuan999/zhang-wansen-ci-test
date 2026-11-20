# -*- coding: utf-8 -*-
"""文档业务服务：上传/异步解析/版本/标签/筛选/删除/导出/下载。"""
import logging
import os
import shutil
import time
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.code import FILE_UPLOAD_FAIL, NOT_FOUND, PARAM_ERROR
from app.core.config import settings
from app.core.response import BizError
from app.models import DocChunk, DocTag, DocTagRel, Document, DownloadApproval, Entity, EntityRelation, VectorOrphan
from app.services.doc_parser import file_hash, parse_document, split_text
from app.services.vector_store import VectorStoreRepository, make_chunk_id

# 标签约束（修复 P2-3）：单个标签最长 32 字，单文档最多 20 个标签
DOC_TAG_MAX_LEN = 32
DOC_TAG_MAX_COUNT = 20

logger = logging.getLogger(__name__)


def _safe_name(name: str) -> str:
    return "".join(c if c not in '<>:"/\\|?*' else "_" for c in name)


def _file_size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


# 文件头魔数签名（防伪造扩展名上传）
_MAGIC_MAP = {
    "pdf": (b"%PDF",),
    "png": (b"\x89PNG\r\n\x1a\n",),
    "jpg": (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
    "docx": (b"PK\x03\x04",),
    "xlsx": (b"PK\x03\x04",),
    "pptx": (b"PK\x03\x04",),
    "txt": (),
    "md": (),
}


def _check_magic(path: str, suffix: str) -> None:
    signatures = _MAGIC_MAP.get(suffix)
    if not signatures:
        return
    with open(path, "rb") as f:
        head = f.read(8)
    if not head.startswith(signatures[0]):
        try:
            os.remove(path)
        except OSError:
            pass
        raise BizError(FILE_UPLOAD_FAIL, "文件内容与扩展名不符，已拒绝上传")


# ===== 逐行注释：上传文件落地（扩展名校验 + 魔数校验 + 防重名落盘） =====
# 1. 白名单扩展名校验：不在 settings.ALLOWED_FILE_TYPES 内直接拒绝。
# 2. 大小校验：超过 MAX_FILE_SIZE_MB 上限拒绝（UploadFile.size 仅 multipart 场景可用）。
# 3. 落盘路径按部门隔离：UPLOAD_DIR/dept_{dept_id}/，避免跨部门文件路径泄露。
# 4. 存储文件名用 uuid4 十六进制 + 原扩展名：天然防重名、防路径注入（原始文件名不落盘）。
# 5. 写盘后 _check_magic：读取文件头 8 字节与魔数签名比对（防伪造扩展名上传可执行文件），
#    不符则删除已落盘文件并抛"文件内容与扩展名不符"。
def save_upload_file(upload: UploadFile, dept_id: int) -> str:
    suffix = Path(upload.filename or "file").suffix.lower().lstrip(".")
    if suffix not in settings.ALLOWED_FILE_TYPES:
        raise BizError(FILE_UPLOAD_FAIL, f"不支持的文件类型: {suffix}")
    if upload.size and upload.size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise BizError(FILE_UPLOAD_FAIL, f"文件超过 {settings.MAX_FILE_SIZE_MB}MB 限制")

    dept_dir = Path(settings.UPLOAD_DIR) / f"dept_{dept_id}"
    dept_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}.{suffix}" if suffix else uuid.uuid4().hex
    dest = dept_dir / stored_name
    try:
        with dest.open("wb") as f:
            shutil.copyfileobj(upload.file, f)
    except Exception as exc:  # pragma: no cover
        logger.error("保存上传文件失败: %s", exc)
        raise BizError(FILE_UPLOAD_FAIL, f"文件保存失败：{exc}")
    # 6. 空文件拦截：0 字节文件无任何可解析内容，落库只会产生空切片污染知识库，直接删除并拒绝
    if dest.stat().st_size == 0:
        try:
            dest.unlink()
        except OSError:
            pass
        raise BizError(FILE_UPLOAD_FAIL, "文件内容为空（0 字节），已拒绝上传")
    _check_magic(str(dest), suffix)
    return str(dest)


def create_document(
    db: Session,
    *,
    dept_id: int,
    user_id: int,
    origin_file_name: str,
    file_path: str,
    file_type: str,
    file_size: int,
    parent_doc_id: int | None = None,
    doc_name: str | None = None,
) -> Document:
    f_hash = file_hash(file_path)
    doc = Document(
        doc_name=doc_name or Path(origin_file_name).stem,
        origin_file_name=origin_file_name,
        file_type=file_type,
        file_size=file_size,
        file_hash=f_hash,
        dept_id=dept_id,
        upload_user_id=user_id,
        parent_doc_id=parent_doc_id,
        status="pending",
        file_path=file_path,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


# ===== 逐行注释：重复文档检测（同部门内去重） =====
# 1. 范围限定：仅查本部门且未删除的文档，避免跨部门同名文件误判。
# 2. 第一优先级：原始文件名 + 文件大小完全一致 -> 视为同一文件的新版本（取版本号最高者）。
# 3. 第二优先级：内容 hash（file_hash，入库时计算）一致 -> 即使改文件名也能识别重复。
# 4. 命中后由调用方决定：复用已有版本记录并清理新上传文件（remove_saved_file），
#    或走上传新版本流程（find_latest_active 找最新版本号 +1）。
def find_duplicate(
    db: Session,
    *,
    dept_id: int,
    origin_file_name: str,
    file_size: int,
    file_hash_value: str,
) -> Document | None:
    """按 文件名+大小 或 内容hash 查找同部门未删除的重复文档。"""
    base = db.query(Document).filter(
        Document.dept_id == dept_id,
        Document.is_deleted.is_(False),
    )
    dup = (
        base.filter(
            Document.origin_file_name == origin_file_name,
            Document.file_size == file_size,
        )
        .order_by(Document.version_no.desc())
        .first()
    )
    if dup:
        return dup
    return (
        base.filter(
            Document.file_hash == file_hash_value,
            Document.file_hash.isnot(None),
            Document.file_hash != "",
        )
        .order_by(Document.version_no.desc())
        .first()
    )


def remove_saved_file(path: str) -> None:
    """清理重复上传时已落盘的临时文件。"""
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        logger.warning("清理重复上传文件失败: %s", path)


# ===== 逐行注释：文档异步解析主流程（上传后由后台线程调用） =====
# 1. 状态机：pending -> processing(progress=10) -> 解析文本(40) -> 切片(70) -> success(100)；
#    任一步异常均捕获置 failed 并写 fail_msg，保证前端可展示失败原因。
# 2. parse_document：按 file_type 分发到对应解析器（pdf/word/excel/ppt/txt/md），返回 (text, extra)；
#    extra.excel_sheet_info 记录 Excel 各 sheet 名称与行数，供对话定位"第几个工作表"。
# 3. 扫描版 PDF（无文本层）：直接置 failed 并提示需 OCR 服务，避免生成空切片污染知识库。
# 4. split_text：按 CHUNK_SIZE / CHUNK_OVERLAP 重叠切片，保证语义连续不截断。
# 5. 每个切片同时写入 doc_chunk 表（结构化检索）与 vector_store（向量检索），
#    chroma_id 作为两边关联的对外 ID；无切片时兜底整篇为 1 个 chunk。
# 6. 内部摘要：优先调用 LLM 生成 80~150 字摘要，LLM 不可用时降级截取正文前 300 字。
def process_document(db: Session, doc_id: int, vector_store: VectorStoreRepository) -> None:
    """异步解析：解析 -> 切片 -> 向量化 -> 更新状态。"""
    doc = db.get(Document, doc_id)
    # P1-6 软删过滤：文档在解析排队期间被软删时直接放弃，避免为回收站文档重建切片与向量
    if not doc or doc.is_deleted:
        return
    doc.status = "processing"
    doc.progress = 10
    db.commit()
    try:
        text, extra = parse_document(doc.file_path, doc.file_type)
        doc.progress = 40
        db.commit()

        if extra and extra.get("excel_sheet_info"):
            doc.excel_sheet_info = extra["excel_sheet_info"]

        # PDF 无文本时标记 scan_pdf（需 OCR 服务）
        if doc.file_type == "pdf" and not text.strip():
            doc.status = "failed"
            doc.fail_msg = "PDF 为扫描件或无文本层，需 OCR 服务支持"
            doc.progress = 100
            db.commit()
            return

        chunks_text = split_text(text, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)
        doc.progress = 70
        db.commit()

        # 按页号/工作表信息补充元数据（简化：按顺序编号）
        chunk_records = []
        vector_chunks = []
        for idx, chunk_text in enumerate(chunks_text):
            cid = make_chunk_id()
            chunk_records.append(
                DocChunk(doc_id=doc.id, chunk_text=chunk_text, page_no=idx + 1, chunk_index=idx, chroma_id=cid)
            )
            vector_chunks.append(
                {
                    "id": cid,
                    "text": chunk_text,
                    "dept_id": doc.dept_id,
                    "page_no": idx + 1,
                    "sheet_name": None,
                }
            )
        # 缺陷修复：无切片兜底分支原来两次调用 make_chunk_id()，导致 doc_chunk.chroma_id 与
        # 向量库中的 id 不一致（双写关联键断裂，删除/检索都对不上），此处复用同一 cid。
        if not chunk_records:
            cid = make_chunk_id()
            chunk_records = [DocChunk(doc_id=doc.id, chunk_text=text, page_no=1, chunk_index=0, chroma_id=cid)]
            vector_chunks = [
                {"id": cid, "text": text, "dept_id": doc.dept_id, "page_no": 1, "sheet_name": None}
            ]

        # ===== 逐行注释：写入方向双写补偿（P1-4） =====
        # 1. 先幂等清掉该文档旧向量（重解析场景），再写新向量；失败按 100/300/700ms 重试 3 次。
        # 2. 向量最终失败：本次不落任何切片行（关系库保持干净），文档置 failed 由用户重解析。
        # 3. 向量成功后提交切片；提交失败则回删刚写入的向量，避免"有向量没切片"的错位数据。
        vector_ok = False
        last_vec_err: Exception | None = None
        for attempt in range(VECTOR_RETRY_TIMES):
            try:
                vector_store.delete_by_doc(doc.id)
                vector_store.add_chunks(doc.id, vector_chunks)
                vector_ok = True
                break
            except Exception as exc:  # pragma: no cover - 依赖外部向量库
                last_vec_err = exc
                logger.warning(
                    "文档 %s 向量写入失败（第 %d/%d 次）: %s", doc.id, attempt + 1, VECTOR_RETRY_TIMES, exc
                )
                if attempt < VECTOR_RETRY_TIMES - 1:
                    time.sleep(VECTOR_RETRY_BACKOFF[min(attempt, len(VECTOR_RETRY_BACKOFF) - 1)])
        if not vector_ok:
            db.query(DocChunk).filter(DocChunk.doc_id == doc.id).delete(synchronize_session=False)
            db.commit()
            doc.status = "failed"
            doc.fail_msg = f"向量库写入失败（已重试 {VECTOR_RETRY_TIMES} 次）：{last_vec_err}"
            doc.progress = 100
            db.commit()
            logger.error("文档 %s 向量写入最终失败，已回滚切片", doc.id)
            return

        try:
            db.add_all(chunk_records)
            db.commit()
        except Exception as exc:  # pragma: no cover
            db.rollback()
            delete_vectors_with_retry(vector_store, doc.id)
            doc.status = "failed"
            doc.fail_msg = f"切片入库失败，已回滚向量：{exc}"
            doc.progress = 100
            db.commit()
            logger.exception("文档 %s 切片入库失败，已回滚向量", doc.id)
            return

        # 生成内部摘要：LLM 优先，失败降级为文本首段
        try:
            from app.services.llm import chat_completion

            snippet = text[:1800]
            msgs = [
                {
                    "role": "system",
                    "content": "你是「知寻 KnowSeek」企业智能文档助手，请用简洁中文为文档生成 80~150 字摘要，突出主题、核心要点与结论，不要使用列表符号。",
                },
                {"role": "user", "content": f"文档标题：{doc.doc_name}\n文档内容片段：\n{snippet}"},
            ]
            summary = chat_completion(db, doc.upload_user_id, msgs, scenario=f"doc_summary_{doc.id}", max_tokens=400).strip()
            doc.summary = summary if summary else (text.strip()[:300] + "…")
        except Exception:
            plain = text.strip()
            doc.summary = plain[:300] + "…" if len(plain) > 300 else plain

        doc.status = "success"
        doc.progress = 100
        db.commit()
        logger.info("文档 %s 解析完成，chunks=%d", doc.id, len(chunks_text))
    except Exception as exc:  # pragma: no cover
        logger.exception("文档 %s 解析失败", doc_id)
        doc.status = "failed"
        doc.fail_msg = str(exc)
        doc.progress = 100
        db.commit()


# ===== 逐行注释：启动恢复（中断解析兜底） =====
# 1. 扫描 pending/processing：这两态代表任务已在内存队列中，进程存活时才会推进。
# 2. 统一置 failed：进程重启后队列丢失，文档无人推进，必须由启动钩子兜底改写状态。
# 3. 写入可操作提示：前端 failed 态会展示该文案并给出"重新解析"入口，用户可自助恢复。
# 4. 返回处理条数：供启动日志输出，便于运维判断是否存在异常重启。
def recover_stuck_documents(db: Session) -> int:
    """服务启动时恢复被中断的解析任务。

    缺陷修复：文档解析通过 BackgroundTask 在进程内执行，进程重启/崩溃后仍处于
    pending/processing 的文档不会被任何进程接管，前端进度条会永久停在解析中，
    且重解析接口会以"正在解析中"拒绝，形成死锁。启动时统一置 failed 且给出可重试提示。
    """
    stuck = (
        db.query(Document)
        .filter(Document.status.in_(["pending", "processing"]), Document.is_deleted.is_(False))
        .all()
    )
    for d in stuck:
        d.status = "failed"
        d.progress = 100
        d.fail_msg = "解析任务因服务重启中断，请点击重新解析"
    if stuck:
        db.commit()
    return len(stuck)


# ===== 逐行注释：重新解析（重试兜底） =====
# 1. 物理清旧切片：doc_chunk 表无 is_deleted 列，切片可完整重建，故直接按 doc_id 删除整批。
# 2. 清向量：调 vector_store.delete_by_doc 删除向量库中该文档全部向量；
#    失败仅告警不中断（避免向量残留阻塞重试，反正重建时会覆盖）。
# 3. 重置状态：status->pending、progress->0、fail_msg 与 excel_sheet_info 清空，
#    让上传进度轮询能重新展示"解析中"。
# 4. 重新走 process_document 完整解析链路（抽取文本 -> 切片 -> 入库 -> 向量化 -> 摘要）。
def reprocess_document(db: Session, doc_id: int, vector_store: VectorStoreRepository) -> None:
    """重试解析：清除旧切片与向量，重置状态后重新走解析流程。

    缺陷修复：原签名第二个参数声明为 Document 对象，但路由以 doc.id（int）投递 BackgroundTask，
    导致内部 doc.id 抛 AttributeError，人工重试解析 100% 失败且异常发生在响应返回之后（前端无感知）。
    此处统一接收 doc_id 并自行加载，同时兼容直接传入 Document 实例的历史调用。
    """
    doc = doc_id if isinstance(doc_id, Document) else db.get(Document, doc_id)
    if not doc:
        logger.warning("重新解析跳过：文档 %s 不存在", doc_id)
        return
    # 缺陷修复：doc_chunk 表无 is_deleted 列（模型仅 id/doc_id/chunk_text/page_no/sheet_name/chunk_index/chroma_id），
    # 原写法引用 DocChunk.is_deleted 直接 AttributeError 使重试解析必崩；切片本身可重建，故改为物理清理。
    db.query(DocChunk).filter(DocChunk.doc_id == doc.id).delete(synchronize_session=False)
    db.commit()
    # 清向量改为带退避重试（P1-4）；仍失败也不阻断，后续 process_document 会先幂等清再写
    if not delete_vectors_with_retry(vector_store, doc.id):
        logger.warning("清除文档 %s 旧向量失败，继续重试解析（重建时会再次覆盖）", doc.id)
    doc.status = "pending"
    doc.progress = 0
    doc.fail_msg = None
    doc.excel_sheet_info = None
    db.commit()
    process_document(db, doc.id, vector_store)


# ===== 逐行注释：文档列表（部门隔离 + 组合筛选 + 分页） =====
# 1. 部门隔离：强制 filter dept_id == 当前部门，且只查未删除（is_deleted=False），
#    杜绝跨部门数据泄露与回收站文档混入列表。
# 2. 筛选链：keyword 匹配 doc_name/origin_file_name（模糊）、file_type 精确、
#    status 精确、tag 走 DocTagRel 关联表按标签名过滤（多标签时前端逗号拆分循环查询）。
# 3. 分页：先 count() 总条数，再按 create_time 倒序取 offset/limit 页数据，
#    返回 (total, docs) 供路由层组装 PageResult。
def list_documents(
    db: Session,
    *,
    dept_id: int,
    keyword: str = "",
    file_type: str = "",
    status: str = "",
    tag: str = "",
    page: int = 1,
    page_size: int = 20,
) -> tuple[int, list[Document]]:
    q = db.query(Document).filter(Document.dept_id == dept_id, Document.is_deleted.is_(False))
    if keyword:
        q = q.filter(or_(Document.doc_name.contains(keyword), Document.origin_file_name.contains(keyword)))
    if file_type:
        q = q.filter(Document.file_type == file_type)
    if status:
        q = q.filter(Document.status == status)
    if tag:
        q = q.join(DocTagRel, DocTagRel.doc_id == Document.id).join(DocTag, DocTag.id == DocTagRel.tag_id).filter(
            DocTag.tag_name == tag
        )
    total = q.count()
    docs = (
        q.order_by(Document.create_time.desc(), Document.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return total, docs


def get_doc_tags(db: Session, doc_id: int) -> list[str]:
    rows = (
        db.query(DocTag.tag_name)
        .join(DocTagRel, DocTagRel.tag_id == DocTag.id)
        .filter(DocTagRel.doc_id == doc_id)
        .order_by(DocTagRel.id.asc())
        .all()
    )
    return [r[0] for r in rows]


def get_tags_map(db: Session, doc_ids: list[int]) -> dict[int, list[str]]:
    """P1-7：批量取多个文档的标签名（一次 IN 查询），供列表页替代逐条 get_doc_tags（N+1）。"""
    ids = {i for i in doc_ids if i is not None}
    if not ids:
        return {}
    rows = (
        db.query(DocTagRel.doc_id, DocTag.tag_name)
        .join(DocTag, DocTag.id == DocTagRel.tag_id)
        .filter(DocTagRel.doc_id.in_(ids))
        .order_by(DocTagRel.id.asc())
        .all()
    )
    out: dict[int, list[str]] = {}
    for doc_id, tag_name in rows:
        out.setdefault(doc_id, []).append(tag_name)
    return out


def assign_tags(db: Session, doc: Document, tag_names: list[str]) -> None:
    """覆盖式设置文档标签。

    P1-7：标签存在性由「逐个 name 查一次」改为「一次 IN 批量查 + 仅对缺失项插入」，
    标签数增长后不再产生 N 次查询。
    修复 P2-3：原实现不校验标签长度/数量，实测 160 字标签也能入库，列表页标签会撑爆卡片。
    现统一在服务层校验（覆盖上传、标签接口、元数据更新三条入口）：单个 ≤32 字、总数 ≤20 个。
    """
    cleaned = [str(n or "").strip() for n in (tag_names or [])]
    cleaned = [n for n in cleaned if n]
    if len(cleaned) > DOC_TAG_MAX_COUNT:
        raise BizError(PARAM_ERROR, f"标签数量过多（最多 {DOC_TAG_MAX_COUNT} 个）")
    too_long = [n for n in cleaned if len(n) > DOC_TAG_MAX_LEN]
    if too_long:
        raise BizError(PARAM_ERROR, f"标签长度超限（单个最多 {DOC_TAG_MAX_LEN} 字）：{too_long[0][:40]}...")
    db.query(DocTagRel).filter(DocTagRel.doc_id == doc.id).delete()
    wanted: list[str] = []
    for name in cleaned:
        if name and name not in wanted:
            wanted.append(name)
    if not wanted:
        db.commit()
        return
    existing = {t.tag_name: t for t in db.query(DocTag).filter(DocTag.tag_name.in_(wanted)).all()}
    for name in wanted:
        tag = existing.get(name)
        if not tag:
            tag = DocTag(tag_name=name)
            db.add(tag)
            db.flush()
            existing[name] = tag
        db.add(DocTagRel(doc_id=doc.id, tag_id=tag.id))
    db.commit()


# ===== 逐行注释：双写补偿工具（P1-4 关系库 / 向量库最终一致） =====
# 策略总览（以关系库为唯一事实来源）：
# 1. 删除方向：先提交关系库事务，再删向量库；向量删除失败按 100/300/700ms 退避重试 3 次，
#    仍失败则写入 vector_orphan 补偿表，由启动钩子 reconcile_vector_orphans 继续重试，
#    保证"已删文档"不会永久残留在向量库被 RAG 命中。
# 2. 写入方向：先写向量库（失败重试后直接判失败，不落任何切片），再提交切片行；
#    切片提交失败则回删本次向量并置 failed，避免出现"有切片没向量"的半成品。
VECTOR_RETRY_TIMES = 3
VECTOR_RETRY_BACKOFF = (0.1, 0.3, 0.7)


def delete_vectors_with_retry(vector_store: VectorStoreRepository, doc_id: int, times: int = VECTOR_RETRY_TIMES) -> bool:
    """删除指定文档向量，失败按退避重试；返回是否最终成功。"""
    for attempt in range(times):
        try:
            if vector_store.delete_by_doc(doc_id, raise_on_error=True):
                return True
            # 返回 False 表示 Chroma 内部已吞异常（非 raise 路径），同样重试
        except Exception as exc:
            logger.warning("删除文档 %s 向量失败（第 %d/%d 次）: %s", doc_id, attempt + 1, times, exc)
        if attempt < times - 1:
            time.sleep(VECTOR_RETRY_BACKOFF[min(attempt, len(VECTOR_RETRY_BACKOFF) - 1)])
    return False


def _enqueue_vector_orphan(db: Session, doc_id: int, error: str) -> None:
    """向量删除最终失败时登记补偿任务（幂等 upsert）。"""
    try:
        row = db.get(VectorOrphan, doc_id)
        if row is None:
            row = VectorOrphan(doc_id=doc_id, retry_count=1, last_error=str(error)[:300])
        else:
            row.retry_count = (row.retry_count or 0) + 1
            row.last_error = str(error)[:300]
            row.update_time = datetime.now()
        db.add(row)
        db.commit()
        logger.error("文档 %s 向量删除失败，已登记双写补偿（vector_orphan）", doc_id)
    except Exception as exc:  # pragma: no cover - 补偿登记失败仅告警
        logger.exception("登记向量补偿失败 doc_id=%s: %s", doc_id, exc)
        db.rollback()


def reconcile_vector_orphans(db: Session, vector_store: VectorStoreRepository) -> int:
    """重放补偿队列：清理"关系库已不存在、向量库仍有残留"的向量。返回清理成功条数。"""
    rows = db.query(VectorOrphan).all()
    if not rows:
        return 0
    # P1-7：原实现循环内逐个 db.get(Document) 判断存活（N+1），改为一次 IN 批量取"未软删"文档 id
    orphan_ids = {r.doc_id for r in rows}
    alive_ids = {
        r[0]
        for r in db.query(Document.id)
        .filter(Document.id.in_(orphan_ids), Document.is_deleted.is_(False))
        .all()
    }
    done = 0
    for row in rows:
        if row.doc_id in alive_ids:
            # 文档仍在且未软删（写入方向回滚场景）：无需清向量，直接移除登记
            db.delete(row)
            db.commit()
            continue
        # P1-6 软删过滤：文档已软删（或物理不存在）时，向量属残留，需继续清理
        if delete_vectors_with_retry(vector_store, row.doc_id):
            db.delete(row)
            db.commit()
            done += 1
        else:
            row.retry_count = (row.retry_count or 0) + 1
            row.last_error = "启动补偿重试仍失败"
            db.commit()
    if done:
        logger.warning("双写补偿：已清理 %d 个文档的残留向量", done)
    return done


def _purge_related_rows(db: Session, doc_id: int) -> dict[str, int]:
    """级联清理文档关联行（不提交，由调用方统一提交/回滚）。

    P1-3 修复：原永久删除只 db.delete(doc)，doc_chunk / doc_tag_rel / entity /
    entity_relation / download_approval 全部残留，形成孤儿数据（demo 实测 doc_id=45
    删文档后仍有切片）。此处按外键依赖顺序清理，并额外清理"指向已删实体的跨文档关系"。
    """
    counts: dict[str, int] = {}
    entity_ids = [r[0] for r in db.query(Entity.id).filter(Entity.doc_id == doc_id).all()]
    q = db.query(EntityRelation).filter(EntityRelation.doc_id == doc_id)
    if entity_ids:
        q = db.query(EntityRelation).filter(
            or_(
                EntityRelation.doc_id == doc_id,
                EntityRelation.source_entity_id.in_(entity_ids),
                EntityRelation.target_entity_id.in_(entity_ids),
            )
        )
    counts["entity_relation"] = q.delete(synchronize_session=False)
    counts["entity"] = db.query(Entity).filter(Entity.doc_id == doc_id).delete(synchronize_session=False)
    counts["doc_chunk"] = db.query(DocChunk).filter(DocChunk.doc_id == doc_id).delete(synchronize_session=False)
    counts["doc_tag_rel"] = db.query(DocTagRel).filter(DocTagRel.doc_id == doc_id).delete(synchronize_session=False)
    counts["download_approval"] = (
        db.query(DownloadApproval).filter(DownloadApproval.doc_id == doc_id).delete(synchronize_session=False)
    )
    return counts


def delete_document(db: Session, doc: Document, vector_store: VectorStoreRepository) -> None:
    """软删除（进回收站）：置删除标记并清掉向量，避免回收站文档仍被检索命中。"""
    doc.is_deleted = True
    doc.update_time = datetime.now()
    db.commit()
    # 补偿：向量删除失败不阻断软删，登记后由 reconcile 兜底重试
    if not delete_vectors_with_retry(vector_store, doc.id):
        _enqueue_vector_orphan(db, doc.id, "软删除时向量库删除失败")


def list_trash(db: Session, dept_id: int, page: int = 1, page_size: int = 20) -> tuple[int, list[Document]]:
    """回收站列表：软删除文档（含解析失败或待解析的占位记录）。"""
    q = db.query(Document).filter(Document.dept_id == dept_id, Document.is_deleted.is_(True))
    total = q.count()
    docs = (
        q.order_by(Document.update_time.desc(), Document.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return total, docs


def restore_documents(db: Session, docs: list[Document]) -> int:
    """批量恢复：置回未删除（向量重建由调用方后台重新解析触发）。"""
    restored = 0
    for doc in docs:
        if doc.is_deleted:
            doc.is_deleted = False
            doc.update_time = datetime.now()
            restored += 1
    db.commit()
    return restored


# ===== 逐行注释：批量永久删除（P1-3 级联 + P1-4 双写补偿） =====
# 执行顺序（关系库为准）：
# 1. 级联清理关联行：entity_relation -> entity -> doc_chunk -> doc_tag_rel -> download_approval；
# 2. 删除文档行并提交：关系库一步到位，提交失败则整体回滚（数据毫发无损，用户可重试）；
# 3. 提交成功后再删向量（带退避重试），失败登记 vector_orphan 由启动钩子补偿；
# 4. 最后删物理文件（失败仅告警，不产生数据不一致，文件路径已无引用）。
def permanent_delete_documents(db: Session, docs: list[Document], vector_store: VectorStoreRepository) -> int:
    """批量永久删除：级联清理关联数据、删向量、删物理文件后移除文档记录。"""
    removed = 0
    for doc in docs:
        doc_id = doc.id
        file_path = doc.file_path
        try:
            _purge_related_rows(db, doc_id)
            db.delete(doc)
            db.commit()  # 关系库提交成功才算删除生效
        except Exception as exc:
            db.rollback()
            logger.exception("永久删除文档 %s 失败，已回滚: %s", doc_id, exc)
            continue
        # 关系库已删 -> 向量库必须追上（重试 + 补偿队列）
        if not delete_vectors_with_retry(vector_store, doc_id):
            _enqueue_vector_orphan(db, doc_id, "永久删除时向量库删除失败")
        if file_path:
            try:
                remove_saved_file(file_path)
            except Exception:  # 文件已不存在等，不阻断
                logger.warning("删除物理文件失败（可忽略）: %s", file_path)
        removed += 1
    return removed


def export_documents_xlsx(db: Session, docs: list[Document]) -> str:
    """导出文档清单为 xlsx，返回文件路径。"""
    try:
        import openpyxl
    except Exception:  # pragma: no cover
        raise BizError(FILE_UPLOAD_FAIL, "导出需要 openpyxl，请先安装依赖")
    export_dir = Path(settings.UPLOAD_DIR) / "export"
    export_dir.mkdir(parents=True, exist_ok=True)
    path = export_dir / f"documents_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "文档清单"
    ws.append(["文档ID", "文档名称", "原始文件名", "类型", "大小(B)", "版本", "状态", "上传时间", "更新时间"])
    for d in docs:
        ws.append(
            [
                d.id,
                d.doc_name,
                d.origin_file_name,
                d.file_type,
                d.file_size,
                d.version_no,
                d.status,
                d.create_time.strftime("%Y-%m-%d %H:%M:%S"),
                d.update_time.strftime("%Y-%m-%d %H:%M:%S"),
            ]
        )
    wb.save(path)
    return str(path)


def find_latest_active(db: Session, origin_file_name: str, dept_id: int) -> Document | None:
    return (
        db.query(Document)
        .filter(
            Document.origin_file_name == origin_file_name,
            Document.dept_id == dept_id,
            Document.is_deleted.is_(False),
        )
        .order_by(Document.version_no.desc())
        .first()
    )
