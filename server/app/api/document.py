# -*- coding: utf-8 -*-
"""文档接口：上传/异步解析/列表/详情/版本/标签/删除/导出/下载。"""
import os

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.code import CONFLICT, NOT_FOUND
from app.core.deps import get_current_user, get_db
from app.core.response import BizError, ok
from app.models import Document, User
from app.schemas.document import AssignTagsReq, BatchDocIdsReq, DocDetail, DocListItem, DocListResp, TrashListItem, UpdateDocMetaReq
from app.services import doc_service
from app.services.audit import record_audit
from app.services.vector_store import VectorStoreRepository

router = APIRouter(prefix="/api/documents", tags=["文档"])
vector_store = VectorStoreRepository()


def _series_versions(db: Session, d: Document) -> list[int]:
    """单个文档所属版本系列的全部版本号（同部门同名文件）。"""
    rows = (
        db.query(Document.version_no)
        .filter(
            Document.origin_file_name == d.origin_file_name,
            Document.dept_id == d.dept_id,
            Document.is_deleted.is_(False),
        )
        .order_by(Document.version_no.asc())
        .all()
    )
    return [v[0] for v in rows]


def _versions_map(db: Session, docs: list[Document]) -> dict[tuple[str, int], list[int]]:
    """P1-7：一次查出列表页所有文档所属版本系列的版本号，避免逐条查版本（N+1）。

    返回 {(origin_file_name, dept_id): [version_no...]}（升序）。
    """
    names = {d.origin_file_name for d in docs if d.origin_file_name}
    depts = {d.dept_id for d in docs if d.dept_id is not None}
    if not names or not depts:
        return {}
    rows = (
        db.query(Document.origin_file_name, Document.dept_id, Document.version_no)
        .filter(
            Document.origin_file_name.in_(names),
            Document.dept_id.in_(depts),
            Document.is_deleted.is_(False),
        )
        .order_by(Document.version_no.asc())
        .all()
    )
    out: dict[tuple[str, int], list[int]] = {}
    for name, dept_id, version_no in rows:
        out.setdefault((name, dept_id), []).append(version_no)
    return out


def _to_item(
    db: Session,
    d: Document,
    tags: list[str] | None = None,
    versions: list[int] | None = None,
) -> DocListItem:
    """文档列表项；tags / versions 可由批量查询预加载传入，避免列表页逐条查库（P1-7）。"""
    if tags is None:
        tags = doc_service.get_doc_tags(db, d.id)
    if versions is None:
        versions = _series_versions(db, d)
    return DocListItem(
        id=d.id,
        doc_name=d.doc_name,
        origin_file_name=d.origin_file_name,
        file_type=d.file_type,
        file_size=d.file_size,
        version_no=d.version_no,
        status=d.status,
        progress=d.progress,
        summary=d.summary,
        create_time=d.create_time,
        update_time=d.update_time,
        tags=tags,
        versions=list(versions),
    )


@router.post("/upload")
async def upload_doc(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    doc_name: str = Form(""),
    tag_names: str = Form(""),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    origin_name = file.filename or "未命名文件"
    path = doc_service.save_upload_file(file, user.dept_id)
    suffix = path.rsplit(".", 1)[-1].lower() if "." in path else ""

    # 上传去重：同部门内 内容hash 完全相同 才拒绝；同名同大小但内容不同则自动升级为新版本
    cur_size = doc_service._file_size(path)
    cur_hash = doc_service.file_hash(path)
    dup = doc_service.find_duplicate(
        db,
        dept_id=user.dept_id,
        origin_file_name=origin_name,
        file_size=cur_size,
        file_hash_value=cur_hash,
    )
    version_parent = None
    if dup:
        # 仅“内容完全一致”才拒绝；同名同大小但内容不同视为新版本，避免误拦合法更新
        if dup.file_hash and dup.file_hash == cur_hash:
            doc_service.remove_saved_file(path)
            raise BizError(CONFLICT, f"文档库已有完全相同的文档，请勿重复上传（命中：{dup.doc_name}）")
        version_parent = dup

    doc = doc_service.create_document(
        db,
        dept_id=user.dept_id,
        user_id=user.id,
        origin_file_name=origin_name,
        file_path=path,
        file_type=suffix,
        file_size=cur_size,
        doc_name=doc_name or None,
        parent_doc_id=version_parent.id if version_parent else None,
    )
    if version_parent:
        doc.version_no = (version_parent.version_no or 1) + 1
        db.commit()
        db.refresh(doc)
    if tag_names:
        tags = [t.strip() for t in tag_names.split(",") if t.strip()]
        if tags:
            doc_service.assign_tags(db, doc, tags)
    background.add_task(doc_service.process_document, db, doc.id, vector_store)
    item = _to_item(db, doc)
    msg = f"同名文件内容已更新，作为 v{doc.version_no} 新版本入库，后台解析中" if version_parent else "上传成功，后台解析中"
    return ok(data=DocDetail(**item.model_dump()).model_dump(mode="json"), message=msg)


@router.get("")
def list_docs(
    keyword: str = Query(""),
    file_type: str = Query(""),
    status: str = Query(""),
    tag: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    total, docs = doc_service.list_documents(
        db, dept_id=user.dept_id, keyword=keyword, file_type=file_type, status=status, tag=tag, page=page, page_size=page_size
    )
    # P1-7：原实现每条文档各查一次标签 + 一次版本链（2N 次查询），改为两次批量查询
    tag_map = doc_service.get_tags_map(db, [d.id for d in docs])
    ver_map = _versions_map(db, docs)
    items = [
        _to_item(
            db,
            d,
            tags=tag_map.get(d.id, []),
            versions=ver_map.get((d.origin_file_name, d.dept_id), [d.version_no]),
        )
        for d in docs
    ]
    return ok(data=DocListResp(total=total, items=items))


@router.get("/export")
def export_docs(
    keyword: str = Query(""),
    file_type: str = Query(""),
    download: bool = Query(False, description="true 时直接返回 xlsx 文件流，便于前端落地保存"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _, docs = doc_service.list_documents(db, dept_id=user.dept_id, keyword=keyword, file_type=file_type, page=1, page_size=10000)
    path = doc_service.export_documents_xlsx(db, docs)
    # 审核修复：原实现仅回传服务器绝对路径，前端无法落地文件且泄露服务端目录结构；
    # download=true 时以 FileResponse 直接回传二进制，兼容旧调用方仍返回路径的 JSON。
    if download:
        return FileResponse(
            path,
            filename=os.path.basename(path),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    return ok(data={"file_path": path}, message="导出成功")


def _to_trash_item(
    db: Session,
    d: Document,
    tags: list[str] | None = None,
    versions: list[int] | None = None,
) -> TrashListItem:
    item = _to_item(db, d, tags=tags, versions=versions)
    return TrashListItem(**item.model_dump(), deleted_time=d.update_time)


@router.get("/trash")
def list_trash(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """文档回收站：软删除文档列表。"""
    total, docs = doc_service.list_trash(db, dept_id=user.dept_id, page=page, page_size=page_size)
    # P1-7：同列表页，标签与版本改为批量预加载
    tag_map = doc_service.get_tags_map(db, [d.id for d in docs])
    ver_map = _versions_map(db, docs)
    items = [
        _to_trash_item(
            db,
            d,
            tags=tag_map.get(d.id, []),
            versions=ver_map.get((d.origin_file_name, d.dept_id), [d.version_no]),
        )
        for d in docs
    ]
    return ok(data=DocListResp(total=total, items=[i.model_dump(mode="json") for i in items]))


@router.post("/trash/batch-restore")
async def batch_restore(
    req: BatchDocIdsReq,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """回收站批量恢复：置回文档库并后台重建向量。"""
    docs = (
        db.query(Document)
        .filter(Document.dept_id == user.dept_id, Document.is_deleted.is_(True), Document.id.in_(req.doc_ids))
        .all()
    )
    restored = doc_service.restore_documents(db, docs)
    for doc in docs:
        if doc.status in ("failed", "success") or doc.file_path:
            background.add_task(doc_service.process_document, db, doc.id, vector_store)
    return ok(data={"restored": restored}, message=f"已恢复 {restored} 个文档")


@router.post("/trash/batch-delete")
def batch_delete_trash(
    req: BatchDocIdsReq,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """回收站批量永久删除：级联清理切片/实体/标签/审批等关联数据、删向量、删物理文件，不可恢复。

    P1-3：级联清理下沉到 doc_service.permanent_delete_documents（同一事务内先删关联行再删主表），
    提交成功后才删向量，向量删除失败进 vector_orphan 补偿队列（P1-4），保证不留孤儿数据。
    """
    docs = (
        db.query(Document)
        .filter(Document.dept_id == user.dept_id, Document.is_deleted.is_(True), Document.id.in_(req.doc_ids))
        .all()
    )
    removed = doc_service.permanent_delete_documents(db, docs, vector_store)
    return ok(data={"removed": removed}, message=f"已永久删除 {removed} 个文档")


@router.post("/trash/{doc_id}/restore")
async def restore_doc(
    doc_id: int,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = db.get(Document, doc_id)
    if not doc or doc.dept_id != user.dept_id or not doc.is_deleted:
        raise BizError(NOT_FOUND, "文档不存在或不在回收站")
    doc_service.restore_documents(db, [doc])
    if doc.file_path:
        background.add_task(doc_service.process_document, db, doc.id, vector_store)
    return ok(data={"doc_id": doc.id}, message="文档已恢复，向量索引后台重建中")


@router.get("/{doc_id}")
def doc_detail(doc_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if not doc or doc.dept_id != user.dept_id or doc.is_deleted:
        raise BizError(NOT_FOUND, "文档不存在")
    # 文档热度：浏览量 +1（智能看板数据来源）
    doc.view_count = (doc.view_count or 0) + 1
    db.commit()
    item = _to_item(db, doc)
    detail = DocDetail(
        **item.model_dump(),
        file_path=doc.file_path,
        fail_msg=doc.fail_msg,
        ocr_content=doc.ocr_content,
        extract_result=doc.extract_result,
    )
    data = detail.model_dump(mode="json")
    # 正文预览：从解析切片（DocChunk）按序拼接，限量返回避免撑爆响应
    from app.models.document import DocChunk

    chunks = (
        db.query(DocChunk)
        .filter(DocChunk.doc_id == doc.id)
        .order_by(DocChunk.chunk_index.asc(), DocChunk.id.asc())
        .all()
    )
    if chunks:
        body = "\n\n".join((c.chunk_text or "") for c in chunks)
        data["content_preview"] = body[:20000]
        data["content_pages"] = len(chunks)
    else:
        data["content_preview"] = ""
        data["content_pages"] = 0
    return ok(data=data)


@router.get("/{doc_id}/download")
def download_doc(doc_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if not doc or doc.dept_id != user.dept_id or doc.is_deleted or not doc.file_path:
        raise BizError(NOT_FOUND, "文档不存在")
    return FileResponse(doc.file_path, filename=doc.origin_file_name)


@router.post("/{doc_id}/tags")
def assign_tags(doc_id: int, req: AssignTagsReq, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if not doc or doc.dept_id != user.dept_id or doc.is_deleted:
        raise BizError(NOT_FOUND, "文档不存在")
    doc_service.assign_tags(db, doc, req.tag_names)
    return ok(data={"tags": doc_service.get_doc_tags(db, doc.id)}, message="标签已更新")


@router.patch("/{doc_id}")
def update_meta(doc_id: int, req: UpdateDocMetaReq, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if not doc or doc.dept_id != user.dept_id or doc.is_deleted:
        raise BizError(NOT_FOUND, "文档不存在")
    if req.doc_name:
        doc.doc_name = req.doc_name
    if req.tag_names is not None:
        doc_service.assign_tags(db, doc, req.tag_names)
    db.commit()
    return ok(data=_to_item(db, doc).model_dump(mode="json"), message="已更新")


@router.get("/{doc_id}/versions")
def list_versions(doc_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """查询文档版本链（同一原始文档的历次上传版本），按版本号倒序返回。

    版本以 parent_doc_id 链式存储，v2.parent=v1、v3.parent=v2，故需沿链回溯到根再广度收集，
    避免只返回一级导致 v3 之后版本丢失。
    """
    doc = db.get(Document, doc_id)
    if not doc or doc.dept_id != user.dept_id or doc.is_deleted:
        raise BizError(NOT_FOUND, "文档不存在")
    root = doc
    hop = 0
    while root.parent_doc_id and hop < 200:
        parent = db.get(Document, root.parent_doc_id)
        if not parent:
            break
        root = parent
        hop += 1
    seen = {root.id}
    frontier = [root.id]
    while frontier:
        children = (
            db.query(Document)
            .filter(Document.parent_doc_id.in_(frontier), Document.is_deleted == False)  # noqa: E712
            .all()
        )
        frontier = [c.id for c in children if c.id not in seen]
        seen.update(frontier)
    rows = (
        db.query(Document)
        # P1-6 软删过滤：seen 集合含根文档与全部子孙，若祖先已软删会把回收站版本混入版本列表
        .filter(Document.id.in_(seen), Document.is_deleted.is_(False))
        .order_by(Document.version_no.desc(), Document.id.desc())
        .all()
    )
    latest = max((r.version_no or 1) for r in rows) if rows else (doc.version_no or 1)
    items = [
        {
            "id": r.id,
            "doc_name": r.doc_name,
            "version_no": r.version_no or 1,
            "status": r.status,
            "file_size": r.file_size,
            "file_type": r.file_type,
            "is_current": (r.version_no or 1) == latest,
            "create_time": str(r.create_time) if getattr(r, "create_time", None) else None,
        }
        for r in rows
    ]
    return ok(data={"total": len(items), "current_version": latest, "items": items})


@router.post("/{doc_id}/versions")
async def upload_new_version(
    doc_id: int,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    old = db.get(Document, doc_id)
    if not old or old.dept_id != user.dept_id or old.is_deleted:
        raise BizError(NOT_FOUND, "文档不存在")
    path = doc_service.save_upload_file(file, user.dept_id)
    suffix = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    new_doc = doc_service.create_document(
        db,
        dept_id=user.dept_id,
        user_id=user.id,
        origin_file_name=old.origin_file_name,
        file_path=path,
        file_type=suffix,
        file_size=doc_service._file_size(path),
        parent_doc_id=old.id,
        doc_name=old.doc_name,
    )
    new_doc.version_no = old.version_no + 1
    db.commit()
    db.refresh(new_doc)
    background.add_task(doc_service.process_document, db, new_doc.id, vector_store)
    return ok(data={"doc_id": new_doc.id, "version_no": new_doc.version_no}, message="新版本已上传，后台解析中")


@router.post("/{doc_id}/reprocess")
async def reprocess_doc(
    doc_id: int,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = db.get(Document, doc_id)
    if not doc or doc.dept_id != user.dept_id or doc.is_deleted:
        raise BizError(NOT_FOUND, "文档不存在")
    if doc.status in ("processing", "pending"):
        raise BizError(CONFLICT, f"文档正在解析中（{doc.status}），请稍后再试")
    # 缺陷修复：原实现直接返回 status="pending" 但未落库，前端刷新仍看到旧的 failed 与旧失败原因；
    # 这里先真实置为 pending 并清空失败原因，再投递后台任务。
    doc.status = "pending"
    doc.progress = 0
    doc.fail_msg = None
    db.commit()
    background.add_task(doc_service.reprocess_document, db, doc.id, vector_store)
    record_audit(db, user, "doc_manual_reprocess", "dept", f"人工触发重新解析文档《{doc.doc_name}》（v{doc.version_no}）")
    return ok(data={"doc_id": doc.id, "status": "pending"}, message="已提交重新解析，完成后列表将自动刷新")


@router.delete("/{doc_id}")
def delete_doc(doc_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if not doc or doc.dept_id != user.dept_id or doc.is_deleted:
        raise BizError(NOT_FOUND, "文档不存在")
    doc_service.delete_document(db, doc, vector_store)
    return ok(message="文档已删除")
