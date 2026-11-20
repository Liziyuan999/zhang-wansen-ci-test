# -*- coding: utf-8 -*-
"""RAG 对话服务：检索 + 溯源 + SSE 流式回答。"""
import asyncio
import json
import logging
from typing import Any, AsyncGenerator

from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.code import NOT_FOUND
from app.core.config import settings
from app.core.response import BizError
from app.core.sensitive import DEFENSIVE_SYSTEM_HINT, filter_sensitive, guard_user_content
from app.models import Conversation, ConversationMsg, Document, Entity, User
from app.services.llm import chat_completion_async
from app.services.vector_store import VectorStoreRepository
from app.services.web_search import search_web

logger = logging.getLogger(__name__)


def create_conv(db: Session, user: User, title: str = "新对话") -> Conversation:
    conv = Conversation(user_id=user.id, title=title)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def list_convs(db: Session, user: User, page: int | None = None, page_size: int | None = None) -> tuple[list[Conversation], int]:
    """会话列表。

    P1-8：原实现全表拉取当前用户全部会话（无上限）。现支持 page/page_size 分页并返回真实总数；
    page 为 None 时退回旧行为（一次返回全部，供内部调用方使用）。
    """
    q = db.query(Conversation).filter(Conversation.user_id == user.id)
    total = q.count() if page is not None else 0
    q = q.order_by(Conversation.update_time.desc(), Conversation.id.desc())
    if page is not None:
        q = q.offset((page - 1) * page_size).limit(page_size)
    convs = q.all()
    return convs, (total if page is not None else len(convs))


def get_conv_detail(db: Session, user: User, conv_id: int) -> tuple[Conversation, list[ConversationMsg]]:
    conv = db.get(Conversation, conv_id)
    if not conv or conv.user_id != user.id:
        raise BizError(NOT_FOUND, "会话不存在")
    msgs = (
        db.query(ConversationMsg)
        .filter(ConversationMsg.conv_id == conv_id)
        .order_by(ConversationMsg.create_time.asc())
        .all()
    )
    return conv, msgs


def delete_conv(db: Session, user: User, conv_id: int) -> None:
    conv = db.get(Conversation, conv_id)
    if not conv or conv.user_id != user.id:
        raise BizError(NOT_FOUND, "会话不存在")
    db.query(ConversationMsg).filter(ConversationMsg.conv_id == conv_id).delete()
    db.delete(conv)
    db.commit()


def _dedupe_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """RAG 引用去重：同一文档同一页（含工作表）的多个切片合并为一条。

    修复 [1][2] 指向同一文档同一页的重复引用：合并后 context 编号、citations、
    ref_ids 三者严格一一对应，避免模型引用角标与前端来源卡片错位。
    """
    deduped: dict[tuple[Any, Any, Any], dict[str, Any]] = {}
    for c in chunks:
        key = (c.get("doc_id"), c.get("page_no"), c.get("sheet_name") or "")
        prev = deduped.get(key)
        if prev is None or (c.get("score", 0), len(c.get("text", ""))) > (
            prev.get("score", 0),
            len(prev.get("text", "")),
        ):
            deduped[key] = c
    return list(deduped.values())


def _build_citations(chunks: list[dict[str, Any]], doc_map: dict[int, str]) -> list[dict[str, Any]]:
    citations = []
    for c in chunks:
        citations.append(
            {
                "chunk_id": c["chunk_id"],
                "doc_id": c["doc_id"],
                "doc_name": doc_map.get(c["doc_id"], f"文档{c['doc_id']}"),
                "content": c["text"][:300],
                "page_no": c.get("page_no"),
                "sheet_name": c.get("sheet_name"),
                "score": c.get("score", 0),
            }
        )
    return citations


async def chat_sse(
    db: Session,
    user: User,
    conv_id: int | None,
    question: str,
    vector_store: VectorStoreRepository,
    web_search: bool = False,
    provider_id: int | None = None,
    doc_ids: list[int] | None = None,
) -> StreamingResponse:
    conv = None
    if conv_id:
        conv = db.get(Conversation, conv_id)
        if not conv or conv.user_id != user.id:
            raise BizError(NOT_FOUND, "会话不存在")
    if not conv:
        conv = create_conv(db, user)

    user_msg = ConversationMsg(conv_id=conv.id, role="user", content=question)
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)
    conv.title = question[:30] if conv.title == "新对话" else conv.title
    db.commit()

    chunks = vector_store.query(question, dept_id=user.dept_id, top_k=settings.RAG_TOP_K, doc_ids=doc_ids)
    # RAG 引用去重：同文档同页切片合并，保证 [i] 角标与 citations 一一对应
    chunks = _dedupe_chunks(chunks)
    doc_ids = list({c["doc_id"] for c in chunks})
    doc_map: dict[int, str] = {}
    if doc_ids:
        # P1-6 软删过滤：命中切片可能指向已进回收站的文档，此处必须排除，
        # 避免已删文档仍作为引用来源展示，也避免给已删文档累加热度。
        docs = db.query(Document).filter(Document.id.in_(doc_ids), Document.is_deleted.is_(False)).all()
        doc_map = {d.id: d.doc_name for d in docs}
        # P1-6 软删过滤：命中切片可能来自回收站文档，剔除后再生成引用角标，避免引用指向已删文档
        chunks = [c for c in chunks if c.get("doc_id") in doc_map]
        doc_ids = list(doc_map.keys())
        # 文档热度：检索命中次数 +1（智能看板数据来源）
        for d in docs:
            d.retrieve_count = (d.retrieve_count or 0) + 1
        db.commit()
    citations = _build_citations(chunks, doc_map)
    ref_ids = [c["chunk_id"] for c in chunks]

    # 关联知识图谱实体：命中文档若有已抽取实体，附带实体列表供前端展示"关联图谱"
    related_entities: list[dict[str, Any]] = []
    if doc_ids:
        kg_entities = (
            db.query(Entity)
            .filter(Entity.doc_id.in_(doc_ids))
            .order_by(Entity.id.desc())
            .limit(30)
            .all()
        )
        related_entities = [
            {
                "id": e.id,
                "name": e.entity_name,
                "type": e.entity_type,
                "description": e.description or "",
                "doc_id": e.doc_id,
            }
            for e in kg_entities
        ]

    context_parts = []
    for i, c in enumerate(chunks, 1):
        src = f"文档:{doc_map.get(c['doc_id'], c['doc_id'])}"
        if c.get("page_no"):
            src += f" 第{c['page_no']}页"
        if c.get("sheet_name"):
            src += f" 工作表:{c['sheet_name']}"
        context_parts.append(f"[{i}] {src}\n{c['text']}")
    context = "\n\n".join(context_parts) or "（未检索到相关内容）"

    # 联网检索：开启时融合实时网络结果（title+url+snippet），失败兜底为空列表；
    # 未开启但本地知识库检索为空（0 条片段）时，自动触发联网兜底并同样推送 web_sources 事件
    web_sources: list[dict[str, Any]] = []
    web_context_parts: list[str] = []
    use_web = web_search
    if web_search:
        try:
            web_sources = await asyncio.to_thread(search_web, question)
        except Exception:  # noqa: BLE001
            web_sources = []
    elif not chunks:
        # 智能联网兜底：本地检索为空时自动补充网络信息（不改变用户开关状态）
        try:
            web_sources = await asyncio.to_thread(search_web, question)
        except Exception:  # noqa: BLE001
            web_sources = []
        if web_sources:
            use_web = True
    for i, w in enumerate(web_sources, 1):
        web_context_parts.append(f"[W{i}] 标题:{w.get('title', '')}\n来源:{w.get('url', '')}\n摘要:{w.get('snippet', '')}")
    web_context = "\n\n".join(web_context_parts) or ("（未获取到网络结果）" if use_web else "")

    system_prompt = (
        "你是「知寻 KnowSeek」企业知识库智能助手，服务对象为企业内部员工。请严格遵循以下回答规范：\n"
        "1. 结论先行：先直接给出明确答案或核心结论，再分点展开依据与细节，结构清晰、逻辑严密；\n"
        "2. 严格依据提供的知识片段作答，引用来源以 [1]、[2] 等角标标注；片段不足以完整回答时，"
        "如实说明「知识库未覆盖该问题」，并给出可操作的下一步建议（如调整提问关键词、上传相关文档），"
        "严禁编造、猜测或提供无依据的信息；\n"
        "3. 语言专业、精炼、正式，采用企业书面语风格，克制得体；涉及制度、流程、数据时优先引用知识库原文表述；\n"
        "4. 不使用口语化表达、表情符号或夸大措辞；不确定之处明确标注，避免误导；\n"
        "5. 如需结合网络信息，以 [W1]、[W2] 角标与知识库来源明确区分，不混淆两种来源。"
        + (
            "同时提供实时网络搜索结果（编号 [W1] [W2] 等），可结合网络信息补充回答，"
            "使用网络来源时以 [W1] 等角标标注。回答末尾不要人为拼接来源列表。"
            if use_web
            else ""
        )
        + "\n\n知识片段：\n"
        + context
        + ("\n\n网络搜索结果：\n" + web_context if use_web else "")
        + "\n\n6. 对话记忆：下方「历史对话」为当前会话上下文。用户在历史中提供的个人信息"
        "（如姓名、身份、偏好）可直接据此回答；当用户提问承接此前内容时，优先从历史对话中理解，"
        "无需依赖知识库检索；历史对话与知识片段相互独立，不要混淆。\n\n"
        + DEFENSIVE_SYSTEM_HINT
    )
    # 对话记忆注入：从库加载当前会话历史（不含刚写入的当前问题），
    # 按最近 N 轮截断防 token 膨胀，注入顺序 system + 历史 user/assistant + 当前 user。
    HISTORY_MAX_ROUNDS = 8  # 最多携带最近 8 轮问答
    history_rows = (
        db.query(ConversationMsg)
        .filter(ConversationMsg.conv_id == conv.id, ConversationMsg.id != user_msg.id)
        .order_by(ConversationMsg.create_time.asc())
        .all()
    )
    history_msgs: list[dict[str, str]] = []
    for m in history_rows:
        if m.role not in ("user", "assistant"):
            continue
        content = (m.content or "").strip()
        if not content:
            continue
        history_msgs.append(
            {
                "role": m.role,
                "content": guard_user_content(content) if m.role == "user" else content,
            }
        )
    # 只保留最近 HISTORY_MAX_ROUNDS 轮（user+assistant 成对截断）
    history_msgs = history_msgs[-HISTORY_MAX_ROUNDS * 2 :]

    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        *history_msgs,
        {"role": "user", "content": guard_user_content(question)},
    ]

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            queue: asyncio.Queue = asyncio.Queue()

            def on_delta(text: str) -> None:
                # 输出侧敏感词过滤：实时打码后入队推送
                safe_text = filter_sensitive(text)
                yield_data = json.dumps({"type": "delta", "content": safe_text}, ensure_ascii=False)
                queue.put_nowait(yield_data)

            yield f"data: {json.dumps({'type': 'citations', 'data': citations, 'related_entities': related_entities}, ensure_ascii=False)}\n\n"
            if web_sources:
                yield f"data: {json.dumps({'type': 'web_sources', 'data': web_sources}, ensure_ascii=False)}\n\n"

            async def _produce() -> str:
                def on_fallback(message: str) -> None:
                    # 供应商调用失败回退时，向前端推送提示事件（在回退模型增量输出之前到达）
                    queue.put_nowait(json.dumps({"type": "fallback", "message": message}, ensure_ascii=False))

                try:
                    return await chat_completion_async(
                        db, user.id, messages, scenario="rag_chat", stream_handler=on_delta,
                        provider_id=provider_id, fallback_handler=on_fallback,
                    )
                finally:
                    queue.put_nowait(None)

            producer = asyncio.create_task(_produce())
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield f"data: {item}\n\n"
            answer = await producer
            answer = filter_sensitive(answer)

            assistant_msg = ConversationMsg(
                conv_id=conv.id, role="assistant", content=answer, ref_chunk_ids=ref_ids
            )
            db.add(assistant_msg)
            db.commit()
            db.refresh(assistant_msg)
            yield f"data: {json.dumps({'type': 'done', 'conv_id': conv.id, 'msg_id': assistant_msg.id}, ensure_ascii=False)}\n\n"
        except Exception as exc:  # pragma: no cover
            logger.exception("SSE 对话异常")
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
