# -*- coding: utf-8 -*-
"""对话接口：会话管理、RAG SSE 流式对话、反馈。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.code import NOT_FOUND, SENSITIVE_CONTENT
from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.core.response import BizError, ok
from app.core.sensitive import contains_sensitive
from app.models import Conversation, ConversationMsg, Feedback, User
from app.schemas.chat import ChatReq, ConvDetail, ConvItem, FeedbackReq, MsgItem, RenameConvReq
from app.services import chat_service
from app.services.llm import get_llm_providers
from app.services.vector_store import VectorStoreRepository

router = APIRouter(prefix="/api/chat", tags=["对话"])
vector_store = VectorStoreRepository()


@router.get("/llm-status")
def llm_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """LLM 配置状态（供前端展示模型接入情况，不暴露密钥）。"""
    providers = get_llm_providers(db)
    return ok(
        data={
            "configured": bool(settings.DEEPSEEK_API_KEY) or bool(providers),
            "model": settings.LLM_MODEL,
            "base_url": settings.LLM_BASE_URL,
            "providers": [
                {
                    "id": p.id,
                    "name": p.name,
                    "base_url": p.base_url,
                    "model": p.model,
                    "is_default": p.is_default,
                    "enabled": p.enabled,
                    "api_key_configured": bool((p.api_key or "").strip()),
                }
                for p in providers
            ],
        }
    )


@router.post("/conversations")
def create_conv(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv = chat_service.create_conv(db, user)
    return ok(data=ConvItem(id=conv.id, title=conv.title, create_time=conv.create_time, update_time=conv.update_time).model_dump(mode="json"))


@router.get("/conversations")
def list_convs(
    page: int | None = Query(None, ge=1, description="不传则保持旧行为：一次返回全部会话"),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """会话列表。

    P1-8：原实现一次性拉取用户全部会话（无上限），现支持分页：传 page 时返回
    {total, page, page_size, items}；不传 page 时保持旧返回结构（纯数组），向后兼容前端。
    """
    convs, total = chat_service.list_convs(db, user, page=page, page_size=page_size)
    data = [ConvItem(id=c.id, title=c.title, create_time=c.create_time, update_time=c.update_time).model_dump(mode="json") for c in convs]
    if page is None:
        return ok(data=data)
    return ok(data={"total": total, "page": page, "page_size": page_size, "items": data})


@router.get("/conversations/{conv_id}")
def conv_detail(conv_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv, msgs = chat_service.get_conv_detail(db, user, conv_id)
    conv_item = ConvItem(id=conv.id, title=conv.title, create_time=conv.create_time, update_time=conv.update_time)
    msg_items = [
        MsgItem(id=m.id, role=m.role, content=m.content, ref_chunk_ids=m.ref_chunk_ids, create_time=m.create_time).model_dump(mode="json")
        for m in msgs
    ]
    return ok(data=ConvDetail(conv=conv_item, messages=msg_items).model_dump(mode="json"))


@router.get("/conversations/{conv_id}/messages")
def conv_messages(
    conv_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = db.get(Conversation, conv_id)
    if not conv or conv.user_id != user.id:
        raise BizError(NOT_FOUND, "会话不存在")
    q = db.query(ConversationMsg).filter(ConversationMsg.conv_id == conv_id)
    total = q.count()
    msgs = q.order_by(ConversationMsg.create_time.desc(), ConversationMsg.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = [
        MsgItem(id=m.id, role=m.role, content=m.content, ref_chunk_ids=m.ref_chunk_ids, create_time=m.create_time).model_dump(mode="json")
        for m in reversed(msgs)
    ]
    return ok(data={"total": total, "page": page, "page_size": page_size, "items": items})


@router.put("/conversations/{conv_id}/rename")
def rename_conv(conv_id: int, req: RenameConvReq, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """重命名会话（历史会话侧边栏管理）。"""
    conv = db.get(Conversation, conv_id)
    if not conv or conv.user_id != user.id:
        raise BizError(NOT_FOUND, "会话不存在")
    conv.title = req.title.strip()[:50]
    db.commit()
    return ok(data=ConvItem(id=conv.id, title=conv.title, create_time=conv.create_time, update_time=conv.update_time).model_dump(mode="json"), message="会话已重命名")


@router.put("/conversations/{conv_id}/reset-context")
def reset_conv_context(conv_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv = db.get(Conversation, conv_id)
    if not conv or conv.user_id != user.id:
        raise BizError(NOT_FOUND, "会话不存在")
    db.query(ConversationMsg).filter(ConversationMsg.conv_id == conv_id).delete()
    conv.is_context_reset = True
    db.commit()
    return ok(message="上下文已重置，后续提问不再携带历史")


@router.delete("/conversations/{conv_id}")
def delete_conv(conv_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    chat_service.delete_conv(db, user, conv_id)
    return ok(message="会话已删除")


@router.post("/ask")
async def chat_ask(req: ChatReq, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # 输入侧敏感词拦截：命中直接拒绝，不进入 LLM
    if contains_sensitive(req.question):
        raise BizError(SENSITIVE_CONTENT, "您的问题包含敏感词，请修改后重试")
    return await chat_service.chat_sse(db, user, req.conv_id, req.question, vector_store, web_search=req.web_search, provider_id=req.model_provider_id, doc_ids=req.doc_ids)


@router.post("/feedback")
def create_feedback(req: FeedbackReq, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    msg = db.get(ConversationMsg, req.msg_id)
    if not msg:
        raise BizError(NOT_FOUND, "消息不存在")
    # 越权兜底：仅允许对本会话所属用户自己的消息提交反馈
    conv = db.get(Conversation, msg.conv_id)
    if not conv or conv.user_id != user.id:
        raise BizError(NOT_FOUND, "消息不存在")
    fb = Feedback(msg_id=msg.id, user_id=user.id, score=req.score, content=req.content)
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return ok(data={"feedback_id": fb.id}, message="反馈已提交")
