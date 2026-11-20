# -*- coding: utf-8 -*-
"""AI 文档 Copilot：对单篇文档提供 提问 / 摘要 / 翻译 / 要点 四种智能动作。

复用 RAG 检索（vector_store.query，doc_ids 限定单文档）与 LLM 生成（chat_completion_async），
返回完整结果 + 引用定位（页码 / 工作表 / 切片），供前端侧栏展示。
"""
import re
from typing import Any

from app.core.code import NOT_FOUND, PARAM_ERROR
from app.core.response import BizError
from app.models import Document, User
from app.models.document import DocChunk
from app.services import vector_store as vs_module
from app.services.llm import chat_completion_async

MAX_CONTEXT_CHARS = 8000

ACTION_LABELS = {
    "ask": "选中文档提问",
    "summary": "一键摘要",
    "translate": "中英互译",
    "outline": "文档要点提炼",
}


def _chunk_citations(chunks: list[dict[str, Any]], doc_name: str) -> list[dict[str, Any]]:
    """将 RAG 检索切片转换为前端可定位的引用列表。"""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for c in chunks:
        key = f"{c.get('page_no')}|{c.get('sheet_name')}|{c.get('chunk_id')}"
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "chunk_id": c.get("chunk_id", ""),
                "doc_id": c.get("doc_id"),
                "doc_name": doc_name,
                "page_no": c.get("page_no"),
                "sheet_name": c.get("sheet_name"),
                "snippet": (c.get("text") or "")[:180],
            }
        )
    return out


def _detect_language(text: str) -> str:
    """粗略语种判定：中文字符占比高 -> zh，否则 en。"""
    if not text:
        return "zh"
    han = len(re.findall(r"[\u4e00-\u9fff]", text))
    return "zh" if han / max(len(text), 1) > 0.12 else "en"


async def run_copilot(
    db,
    user: User,
    doc_id: int,
    action: str,
    source_text: str = "",
    question: str = "",
) -> dict[str, Any]:
    # ===== 逐行注释：文档 Copilot 四动作统一入口（核心）=====
    # 1. 动作白名单校验：仅支持 ask/summary/translate/outline，其余抛 PARAM_ERROR；
    # 2. 文档归属校验：文档必须存在、未删除且 dept_id 与用户一致（部门级数据隔离）；
    # 3. 读取文档全部切片并按 chunk_index 排序拼接为正文，用于摘要/翻译/要点上下文；
    # 4. 上下文策略：优先使用前端传来的选中片段 source_text，否则取整篇正文前 8000 字符；
    # 5. 四种动作各自构造 Prompt 与 system 角色（"知寻 KnowSeek 文档 Copilot"），
    #    并针对动作做差异化的引用定位：
    #    - ask：走 RAG 向量检索（vector_store.query 限定 doc_ids=[doc.id]）生成 citations，
    #      无选中片段时用检索命中的切片作为问答上下文；
    #    - summary/translate/outline：直接用文档正文切片构造 citations（页码/工作表定位）；
    # 6. chat_completion_async() 异步调用大模型（scenario=copilot，temperature=0.4）生成回答；
    # 7. 返回 answer + citations + 请求回显（action/source_text/question/doc 信息），供前端侧栏渲染。
    if action not in ACTION_LABELS:
        raise BizError(PARAM_ERROR, f"不支持的 Copilot 动作: {action}")

    doc = db.get(Document, doc_id)
    if not doc or doc.dept_id != user.dept_id or doc.is_deleted:
        raise BizError(NOT_FOUND, "文档不存在")

    # 读取文档全部切片，用于摘要/要点/翻译上下文
    chunks = (
        db.query(DocChunk)
        .filter(DocChunk.doc_id == doc.id)
        .order_by(DocChunk.chunk_index.asc(), DocChunk.id.asc())
        .all()
    )
    doc_body = "\n\n".join((c.chunk_text or "") for c in chunks)

    # 选中片段优先作为上下文，否则回退整篇正文
    context = (source_text or "").strip() or doc_body[:MAX_CONTEXT_CHARS]
    # 修复 P2-4：文档还没有可用的切片正文、且用户也没有选中片段时，
    # 原实现会拿空上下文去调 LLM，返回一段空泛内容却提示"处理完成"，白耗一次调用额度。
    # 现改为明确拒绝，提示用户等待解析完成或重新上传。
    if not context.strip():
        raise BizError(PARAM_ERROR, "该文档暂无可用正文（可能仍在解析中或解析失败），请稍后重试或重新解析")

    vector_store = vs_module.VectorStoreRepository()
    citations: list[dict[str, Any]] = []

    if action == "ask":
        user_question = (question or "").strip() or "请根据以上文档内容回答我的问题"
        # 有选中片段时，片段即权威上下文；同时做 RAG 检索补充引用定位
        rag = vector_store.query(user_question, dept_id=user.dept_id, top_k=6, doc_ids=[doc.id])
        citations = _chunk_citations(rag, doc.doc_name)
        if context != source_text:
            # 无选中片段时以 RAG 命中的切片作为上下文
            context = "\n\n".join(f"[{i}] {c.get('text', '')}" for i, c in enumerate(rag[:6], 1)) or context
        prompt = (
            f"用户正在阅读企业知识库文档《{doc.doc_name}》，就其中内容提出如下问题。\n"
            f"请严格依据提供的文档片段作答，结论先行、结构清晰，引用来源用 [1]、[2] 等角标标注。\n"
            f"文档片段：\n{context}\n\n用户问题：{user_question}"
        )
        messages = [
            {"role": "system", "content": "你是「知寻 KnowSeek」文档 Copilot，专注就当前文档内容精准作答，严禁编造或提供文档外信息。"},
            {"role": "user", "content": prompt},
        ]
    elif action == "summary":
        prompt = (
            f"请为以下企业知识库文档《{doc.doc_name}》生成一份结构化摘要（结论先行）：\n"
            f"1. 核心主旨（1-2 句）\n2. 关键内容（分点）\n3. 业务价值或使用建议\n"
            f"控制在 400 字以内，企业书面风格。\n\n文档内容：\n{context[:MAX_CONTEXT_CHARS]}"
        )
        messages = [
            {"role": "system", "content": "你是「知寻 KnowSeek」文档 Copilot，擅长提炼文档摘要，结论先行、克制专业。"},
            {"role": "user", "content": prompt},
        ]
        citations = _chunk_citations(
            [{"chunk_id": c.id, "doc_id": doc.id, "page_no": c.page_no, "sheet_name": c.sheet_name, "text": c.chunk_text} for c in chunks[:6]],
            doc.doc_name,
        )
    elif action == "translate":
        target = "英文" if _detect_language(context) == "zh" else "中文"
        prompt = (
            f"请将以下内容翻译为{target}，保持专业书面语气，不得增删原意，逐句完整翻译：\n\n{context[:MAX_CONTEXT_CHARS]}"
        )
        messages = [
            {"role": "system", "content": f"你是资深企业级翻译专家，只输出翻译结果，不输出解释。"},
            {"role": "user", "content": prompt},
        ]
        citations = _chunk_citations(
            [{"chunk_id": c.id, "doc_id": doc.id, "page_no": c.page_no, "sheet_name": c.sheet_name, "text": c.chunk_text} for c in chunks[:4]],
            doc.doc_name,
        )
    elif action == "outline":
        prompt = (
            f"请为以下企业知识库文档《{doc.doc_name}》提炼文档要点，输出结构化大纲：\n"
            f"以「一、/（一）/1.」层级分条呈现，每条要点一句话概括，总要点不超过 12 条，企业书面风格：\n\n"
            f"文档内容：\n{context[:MAX_CONTEXT_CHARS]}"
        )
        messages = [
            {"role": "system", "content": "你是「知寻 KnowSeek」文档 Copilot，擅长提炼结构化要点大纲。"},
            {"role": "user", "content": prompt},
        ]
        citations = _chunk_citations(
            [{"chunk_id": c.id, "doc_id": doc.id, "page_no": c.page_no, "sheet_name": c.sheet_name, "text": c.chunk_text} for c in chunks[:8]],
            doc.doc_name,
        )

    answer = await chat_completion_async(db, user.id, messages, scenario="copilot", temperature=0.4, max_tokens=2400)

    return {
        "action": action,
        "action_label": ACTION_LABELS[action],
        "answer": answer,
        "citations": citations,
        "source_text": source_text or "",
        "question": question or "",
        "doc_id": doc.id,
        "doc_name": doc.doc_name,
    }
