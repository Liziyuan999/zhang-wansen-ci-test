# -*- coding: utf-8 -*-
"""AI 周报：基于 LangGraph 的企业周报生成工作流。

工作流节点：collect_data（聚合周期数据）→ generate_draft（LLM 生成草稿）
→ refine（质检修订）。LLM 复用 DeepSeek 接入（chat_completion），
无 Key 或异常时降级为「模板骨架 + 聚合数据」兜底输出。
"""
import json
import logging
import operator
import time
from datetime import date, datetime, timedelta
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.models import AgentTask, Conversation, ConversationMsg, Department, Document, OperationLog, Team, User
from app.services.llm import chat_completion

logger = logging.getLogger(__name__)

try:  # LangChain 模板（可选依赖，未安装时回退 f-string）
    from langchain_core.prompts import PromptTemplate

    HAS_LANGCHAIN = True
except Exception:  # pragma: no cover
    HAS_LANGCHAIN = False

# 企业周报模板骨架（预置章节）
TEMPLATE_SECTIONS = [
    {"key": "overview", "title": "一、本周概览"},
    {"key": "knowledge", "title": "二、知识资产动态"},
    {"key": "chat", "title": "三、对话与检索"},
    {"key": "agent", "title": "四、Agent 运行情况"},
    {"key": "organization", "title": "五、组织协作"},
    {"key": "next", "title": "六、下周建议"},
]

PROMPT_TEMPLATE = """你是「知寻 KnowSeek」的企业运营分析师。请基于以下周期数据撰写一份结构化中文周报。
周报章节固定为：一、本周概览；二、知识资产动态；三、对话与检索；四、Agent 运行情况；五、组织协作；六、下周建议。
要求：数据引用准确、结论有依据、语言专业简洁、每个章节 2-4 句话，输出 Markdown 格式。

统计周期：{period}
{data}
请直接输出周报 Markdown。"""


class ReportState(TypedDict, total=False):
    user_id: int
    start_date: str
    end_date: str
    data: dict[str, Any]
    draft: str
    final: str
    trace: Annotated[list[dict[str, Any]], operator.add]


def _prompt_text(template: str, **kwargs) -> str:
    if HAS_LANGCHAIN:
        try:
            return PromptTemplate.from_template(template).format(**kwargs)
        except Exception:  # pragma: no cover
            pass
    return template.format(**kwargs)


def collect_data_node(ctx: dict[str, Any], state: ReportState) -> dict[str, Any]:
    t0 = time.monotonic()
    db = ctx["db"]
    start = datetime.strptime(state["start_date"], "%Y-%m-%d")
    end = datetime.strptime(state["end_date"], "%Y-%m-%d") + timedelta(days=1)

    doc_total = db.query(Document.id).filter(Document.is_deleted.is_(False)).count()
    doc_new = db.query(Document.id).filter(Document.is_deleted.is_(False), Document.create_time >= start, Document.create_time < end).count()
    doc_status = {s: c for s, c in db.query(Document.status, func_count(db, Document)).filter(Document.is_deleted.is_(False), Document.create_time >= start, Document.create_time < end).group_by(Document.status).all()}

    chat_count = db.query(Conversation.id).filter(Conversation.create_time >= start, Conversation.create_time < end).count()
    msg_count = db.query(ConversationMsg.id).filter(ConversationMsg.create_time >= start, ConversationMsg.create_time < end).count()
    retrieval_count = db.query(OperationLog.id).filter(OperationLog.module == "chat", OperationLog.create_time >= start, OperationLog.create_time < end).count()

    agent_total = db.query(AgentTask.id).filter(AgentTask.create_time >= start, AgentTask.create_time < end).count()
    agent_done = db.query(AgentTask.id).filter(AgentTask.create_time >= start, AgentTask.create_time < end, AgentTask.status == "done").count()
    agent_failed = db.query(AgentTask.id).filter(AgentTask.create_time >= start, AgentTask.create_time < end, AgentTask.status == "failed").count()
    agent_by_type = {t: c for t, c in db.query(AgentTask.task_type, func_count(db, AgentTask)).filter(AgentTask.create_time >= start, AgentTask.create_time < end).group_by(AgentTask.task_type).all()}

    users = db.query(User.id).count()
    depts = db.query(Department.id).count()
    teams = db.query(Team.id).count()
    new_users = db.query(User.id).filter(User.create_time >= start, User.create_time < end).count()

    data = {
        "period": f"{state['start_date']} ~ {state['end_date']}",
        "knowledge": {"doc_total": doc_total, "doc_new": doc_new, "doc_status": doc_status},
        "chat": {"conversations": chat_count, "messages": msg_count, "retrievals": retrieval_count},
        "agent": {"total": agent_total, "done": agent_done, "failed": agent_failed, "by_type": agent_by_type},
        "organization": {"users": users, "new_users": new_users, "departments": depts, "teams": teams},
    }
    return {"data": data, "trace": [{"node": "collect", "name": "数据聚合", "status": "ok", "summary": f"聚合周期 {data['period']} 的知识库/对话/Agent/组织数据", "cost_ms": int((time.monotonic() - t0) * 1000)}]}


def generate_draft_node(ctx: dict[str, Any], state: ReportState) -> dict[str, Any]:
    t0 = time.monotonic()
    data = state["data"]
    text = json.dumps(data, ensure_ascii=False, indent=2)
    prompt = _prompt_text(PROMPT_TEMPLATE, period=data["period"], data=text)
    try:
        draft = chat_completion(ctx["db"], ctx["user"].id, [{"role": "user", "content": prompt}], scenario="weekly_report", temperature=0.6, max_tokens=4000, provider_id=ctx.get("provider_id"))
        return {"draft": draft, "fallback": False, "trace": [{"node": "generate", "name": "LLM 生成", "status": "ok", "summary": "生成周报草稿", "cost_ms": int((time.monotonic() - t0) * 1000)}]}
    except Exception as exc:  # noqa: BLE001
        logger.warning("周报生成失败，降级为模板兜底: %s", exc)
        return {"draft": _fallback_draft(data), "fallback": True, "trace": [{"node": "generate", "name": "LLM 生成", "status": "degraded", "summary": "LLM 不可用，降级为模板骨架兜底", "cost_ms": int((time.monotonic() - t0) * 1000)}]}


def refine_node(ctx: dict[str, Any], state: ReportState) -> dict[str, Any]:
    t0 = time.monotonic()
    draft = state.get("draft", "")
    prompt = (
        "请审阅下面的周报，检查：1) 六个章节是否完整；2) 数字是否与上文统计一致；"
        "3) 表达是否专业。如无问题输出【无问题】，否则输出修订后的完整周报。\n\n周报：\n" + draft[:6000]
    )
    try:
        final = chat_completion(ctx["db"], ctx["user"].id, [{"role": "user", "content": prompt}], scenario="weekly_report_refine", temperature=0.3, max_tokens=4000, provider_id=ctx.get("provider_id"))
        final = final if "无问题" not in final else draft
    except Exception:  # noqa: BLE001
        final = draft
    return {"final": final, "trace": [{"node": "refine", "name": "质检修订", "status": "ok", "summary": "完成质检与修订", "cost_ms": int((time.monotonic() - t0) * 1000)}]}


def func_count(db, model):
    from sqlalchemy import func

    return func.count(model.id)


def _fallback_draft(data: dict[str, Any]) -> str:
    """降级兜底：模板骨架 + 聚合数据直接填充。"""
    k = data["knowledge"]
    c = data["chat"]
    a = data["agent"]
    o = data["organization"]
    status_txt = "、".join(f"{s}:{v}" for s, v in (k.get("doc_status") or {}).items()) or "无新增"
    type_txt = "、".join(f"{t}:{v}" for t, v in (a.get("by_type") or {}).items()) or "无"
    return (
        f"# 知寻 KnowSeek 企业周报（{data['period']}）\n\n"
        f"## 一、本周概览\n本周知识库新增文档 {k['doc_new']} 篇（累计 {k['doc_total']} 篇），"
        f"产生对话 {c['conversations']} 次、消息 {c['messages']} 条，检索 {c['retrievals']} 次，"
        f"Agent 任务 {a['total']} 个，整体运行平稳。\n\n"
        f"## 二、知识资产动态\n新增文档状态分布：{status_txt}。\n\n"
        f"## 三、对话与检索\n本周对话 {c['conversations']} 次、消息 {c['messages']} 条、检索 {c['retrievals']} 次，知识调用活跃。\n\n"
        f"## 四、Agent 运行情况\n本周 Agent 任务共 {a['total']} 个（成功 {a['done']}、失败 {a['failed']}），类型分布：{type_txt}。\n\n"
        f"## 五、组织协作\n当前组织规模：用户 {o['users']} 人（新增 {o['new_users']}）、部门 {o['departments']} 个、团队 {o['teams']} 个。\n\n"
        f"## 六、下周建议\n建议持续补充知识资产、关注失败 Agent 任务并优化检索质量。"
    )


def run_weekly_report(db, user, start_date: str, end_date: str, focus: str = "", provider_id: int | None = None) -> tuple[str, list[dict[str, Any]], bool]:
    """执行周报生成工作流，返回 (最终 Markdown, 节点轨迹, 是否降级兜底)。"""
    ctx = {"db": db, "user": user, "provider_id": provider_id}
    graph = StateGraph(ReportState)
    graph.add_node("collect", lambda s: collect_data_node(ctx, s))
    graph.add_node("generate", lambda s: generate_draft_node(ctx, s))
    graph.add_node("refine", lambda s: refine_node(ctx, s))
    graph.add_edge(START, "collect")
    graph.add_edge("collect", "generate")
    graph.add_edge("generate", "refine")
    graph.add_edge("refine", END)
    app = graph.compile()
    init = {"user_id": user.id, "start_date": start_date, "end_date": end_date}
    if focus:
        init["focus"] = focus
    result = app.invoke(init)
    return result.get("final") or result.get("draft") or "", result.get("trace", []), bool(result.get("fallback", False))
