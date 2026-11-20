# -*- coding: utf-8 -*-
"""AI 文档 Copilot 接口：POST /api/document/copilot。

动作支持 ask（选中文档提问）/ summary（一键摘要）/ translate（中英互译）/ outline（文档要点提炼）。
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.code import PARAM_ERROR
from app.core.deps import get_current_user, get_db
from app.core.response import BizError, ok
from app.models import User
from app.services.copilot_service import run_copilot

router = APIRouter(prefix="/api/document", tags=["文档 Copilot"])


class CopilotReq(BaseModel):
    doc_id: int = Field(..., description="文档 ID")
    action: str = Field(..., description="动作: ask/summary/translate/outline")
    source_text: str = Field("", description="选中的正文片段（可选）")
    question: str = Field("", description="用户问题（ask 时使用）")


COPILOT_ACTIONS = ("ask", "summary", "translate", "outline")


# ===== 逐行注释：文档 Copilot 路由层 =====
# 1. 请求体 CopilotReq：doc_id（文档）、action（ask/summary/translate/outline）、
#    source_text（前端选中的正文片段，可选）、question（ask 动作的问题，可选）；
# 2. 本接口为异步端点，await run_copilot 内部分发到 RAG 检索与 LLM 调用；
# 3. 返回统一 ok 包裹：data 内含 answer + citations（引用定位）+ 请求回显。
# 4. 修复 P2-4：入参前置校验——非法 action、ask 动作缺问题、无有效文本（既无选中片段也无可检索正文）
#    时直接返回 10001，不再白白调用一次 LLM（此前空文本会返回"完成"且消耗额度）。
@router.post("/copilot")
async def document_copilot(
    req: CopilotReq,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    action = (req.action or "").strip().lower()
    if action not in COPILOT_ACTIONS:
        raise BizError(PARAM_ERROR, f"不支持的动作：{req.action}，可选 ask/summary/translate/outline")
    question = (req.question or "").strip()
    source_text = (req.source_text or "").strip()
    # ask 动作既没有问题也没有选中片段时，属于无意义请求：直接拒绝，不调用 LLM
    if action == "ask" and not question and not source_text:
        raise BizError(PARAM_ERROR, "请填写要提问的问题，或先选中需要提问的正文片段")
    data = await run_copilot(db, user, req.doc_id, action, source_text, question)
    return ok(data=data, message="Copilot 处理完成")
