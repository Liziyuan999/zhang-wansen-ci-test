# -*- coding: utf-8 -*-
"""LangGraph 多节点工作流编排：规划 → 检索 → 生成 → 反思 → 精修。

围绕 LangGraph/LangChain 构建企业级 Agent 工作流，用于 Agent 任务生成：
  - plan:     根据任务类型与用户补充要求生成执行计划与检索意图
  - retrieve: 基于 RAG（+可选联网）构建上下文
  - generate: 基于计划与上下文生成初稿
  - reflect:  按质量检查清单对初稿进行反思，输出问题清单
  - refine:   依据反思意见生成最终交付稿（无问题则直接采用初稿）

状态图使用 LangGraph StateGraph 编排，节点为可独立复用的有状态步骤，
全程记录每个节点的执行摘要与耗时，供前端「工作流轨迹」时间线展示。
"""
import json
import logging
import operator
import time
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.services import agent_service
from app.services.llm import chat_completion

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 工作流状态
# ---------------------------------------------------------------------------


class WfState(TypedDict, total=False):
    task_id: int
    user_id: int
    task_type: str
    plan: str
    queries: list[str]
    context: str
    web_sources: list[dict[str, Any]]
    draft: str
    reflection: str
    issues: list[str]
    final: str
    trace: Annotated[list[dict[str, Any]], operator.add]


# ---------------------------------------------------------------------------
# 节点实现（闭包注入 db / user / task / vector_store，避免将 Session 放入图状态）
# ---------------------------------------------------------------------------


def _llm(db, user_id: int, messages: list[dict[str, str]], scenario: str, provider_id: int | None = None) -> str:
    return chat_completion(db, user_id, messages, scenario=scenario, temperature=0.6, max_tokens=3000, provider_id=provider_id)


def _json_extract(text: str) -> dict[str, Any] | None:
    """从 LLM 输出中提取 JSON（支持纯 JSON 或包裹 ```json 代码块）。"""
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    try:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            return json.loads(raw[start : end + 1])
    except Exception:  # noqa: BLE001
        return None
    return None


def plan_node(ctx: dict[str, Any], state: WfState) -> dict[str, Any]:
    t0 = time.monotonic()
    task_type = state["task_type"]
    extra = (ctx["task"].params or {}).get("extra")
    extra_txt = f"\n用户补充要求：{extra}" if extra else ""
    prompt = (
        "你是企业智能 Agent 的规划器。请为下面的文档生成任务制定一份可执行计划，"
        "并给出 1-3 条用于知识库检索的关键查询（覆盖任务主题的不同角度）。\n"
        f"任务类型：{task_type}\n{extra_txt}\n"
        '请严格输出 JSON：{"plan": "计划说明（2-4 句）", "queries": ["查询1", "查询2"]}'
    )
    try:
        raw = _llm(ctx["db"], ctx["user"].id, [{"role": "user", "content": prompt}], scenario="wf_plan", provider_id=ctx.get("provider_id"))
        parsed = _json_extract(raw) or {}
        plan = str(parsed.get("plan") or raw[:300])
        queries = parsed.get("queries") or agent_service.DEFAULT_QUERIES.get(task_type, ["知识检索"])
        queries = [str(q) for q in queries][:3]
    except Exception as exc:  # noqa: BLE001
        logger.warning("规划节点失败，使用默认计划: %s", exc)
        plan = "基于任务类型执行标准检索与生成流程。"
        queries = agent_service.DEFAULT_QUERIES.get(task_type, ["知识检索"])
    node_trace = {
        "node": "plan",
        "name": "任务规划",
        "status": "ok",
        "summary": plan[:120],
        "cost_ms": int((time.monotonic() - t0) * 1000),
    }
    return {"plan": plan, "queries": queries, "trace": [node_trace]}


def retrieve_node(ctx: dict[str, Any], state: WfState) -> dict[str, Any]:
    t0 = time.monotonic()
    task = ctx["task"]
    db = ctx["db"]
    user = ctx["user"]
    vector_store = ctx["vector_store"]
    queries = state.get("queries") or agent_service.DEFAULT_QUERIES.get(state["task_type"], ["知识检索"])
    try:
        chunks = agent_service._retrieve_for_task(db, user, state["task_type"], task.selected_doc_ids or [], vector_store)
    except Exception as exc:  # noqa: BLE001
        chunks = []
        logger.warning("工作流检索失败: %s", exc)
    context = agent_service.build_context_text(chunks, task.web_sources or [])
    node_trace = {
        "node": "retrieve",
        "name": "知识检索",
        "status": "ok",
        "summary": f"命中 {len(chunks)} 条知识片段，查询意图：{queries[0]}",
        "cost_ms": int((time.monotonic() - t0) * 1000),
    }
    return {"context": context, "web_sources": task.web_sources or [], "trace": [node_trace]}


def generate_node(ctx: dict[str, Any], state: WfState) -> dict[str, Any]:
    t0 = time.monotonic()
    task = ctx["task"]
    context = state.get("context", "（未检索到相关内容）")
    prompt_template = agent_service.TASK_PROMPTS.get(state["task_type"], "请根据以下内容生成结果")
    extra = (task.params or {}).get("extra")
    prompt = prompt_template
    if extra:
        from app.core.sensitive import guard_user_content

        prompt = f"{prompt}\n\n用户补充要求：{guard_user_content(str(extra))}"
    system = (
        "你是「知寻 KnowSeek」企业智能 Agent。请基于以下执行计划与知识片段生成初稿，"
        "并正确标注引用来源。\n\n执行计划：\n"
        + state.get("plan", "")
        + "\n\n知识片段：\n"
        + context
    )
    try:
        draft = _llm(ctx["db"], ctx["user"].id, [{"role": "system", "content": system}, {"role": "user", "content": prompt}], scenario="wf_generate", provider_id=ctx.get("provider_id"))
    except Exception as exc:  # noqa: BLE001
        draft = f"（生成失败：{exc}）"
    node_trace = {
        "node": "generate",
        "name": "内容生成",
        "status": "ok",
        "summary": draft[:120],
        "cost_ms": int((time.monotonic() - t0) * 1000),
    }
    return {"draft": draft, "trace": [node_trace]}


def reflect_node(ctx: dict[str, Any], state: WfState) -> dict[str, Any]:
    t0 = time.monotonic()
    draft = state.get("draft", "")
    prompt = (
        "你是企业内容质检员。请审阅下面的初稿，按检查清单评估：\n"
        "1) 结构是否完整（背景/结论/计划等）；2) 内容是否与知识片段一致、有无虚构；"
        "3) 是否遗漏用户补充要求；4) 表达是否清晰专业。\n"
        "请严格输出 JSON：{\"issues\": [\"问题1\", \"问题2\"], \"score\": 8}\n"
        "如果没有问题，issues 输出空数组。\n\n初稿：\n"
        + draft[:4000]
    )
    try:
        raw = _llm(ctx["db"], ctx["user"].id, [{"role": "user", "content": prompt}], scenario="wf_reflect", provider_id=ctx.get("provider_id"))
        parsed = _json_extract(raw) or {}
        issues = [str(i) for i in (parsed.get("issues") or [])][:6]
        reflection = raw[:400]
    except Exception as exc:  # noqa: BLE001
        issues = []
        reflection = f"（反思节点失败：{exc}）"
    node_trace = {
        "node": "reflect",
        "name": "质量反思",
        "status": "ok",
        "summary": f"发现 {len(issues)} 个问题" + (f"：{issues[0]}" if issues else "，未发现明显问题"),
        "cost_ms": int((time.monotonic() - t0) * 1000),
    }
    return {"reflection": reflection, "issues": issues, "trace": [node_trace]}


def refine_node(ctx: dict[str, Any], state: WfState) -> dict[str, Any]:
    t0 = time.monotonic()
    draft = state.get("draft", "")
    issues = state.get("issues", [])
    if not issues:
        return {"final": draft, "trace": [{"node": "refine", "name": "精修定稿", "status": "ok", "summary": "反思无问题，直接采用初稿", "cost_ms": 0}]}
    prompt = (
        "你是企业智能 Agent 的终审编辑。请根据质检问题清单对初稿进行针对性修改，"
        "输出最终交付稿（保持原有结构，修正问题，不要引入知识片段之外的新事实）。\n\n"
        f"问题清单：\n" + "\n".join(f"- {i}" for i in issues) + "\n\n初稿：\n" + draft
    )
    try:
        final = _llm(ctx["db"], ctx["user"].id, [{"role": "user", "content": prompt}], scenario="wf_refine", provider_id=ctx.get("provider_id"))
    except Exception as exc:  # noqa: BLE001
        final = draft
    node_trace = {
        "node": "refine",
        "name": "精修定稿",
        "status": "ok",
        "summary": f"依据 {len(issues)} 个问题完成修订",
        "cost_ms": int((time.monotonic() - t0) * 1000),
    }
    return {"final": final, "trace": [node_trace]}


# ---------------------------------------------------------------------------
# 入口：运行 LangGraph 工作流
# ---------------------------------------------------------------------------


def run_langgraph_workflow(db, user, task, vector_store, provider_id: int | None = None) -> tuple[str, list[dict[str, Any]]]:
    """执行规划→检索→生成→反思→精修工作流，返回 (最终结果, 节点轨迹)。"""
    ctx: dict[str, Any] = {"db": db, "user": user, "task": task, "vector_store": vector_store, "provider_id": provider_id}

    def _plan(s: WfState) -> dict[str, Any]:
        return plan_node(ctx, s)

    def _retrieve(s: WfState) -> dict[str, Any]:
        return retrieve_node(ctx, s)

    def _generate(s: WfState) -> dict[str, Any]:
        return generate_node(ctx, s)

    def _reflect(s: WfState) -> dict[str, Any]:
        return reflect_node(ctx, s)

    def _refine(s: WfState) -> dict[str, Any]:
        return refine_node(ctx, s)

    builder = StateGraph(WfState)
    builder.add_node("plan", _plan)
    builder.add_node("retrieve", _retrieve)
    builder.add_node("generate", _generate)
    builder.add_node("reflect", _reflect)
    builder.add_node("refine", _refine)
    builder.add_edge(START, "plan")
    builder.add_edge("plan", "retrieve")
    builder.add_edge("retrieve", "generate")
    builder.add_edge("generate", "reflect")
    builder.add_edge("reflect", "refine")
    builder.add_edge("refine", END)
    graph = builder.compile()

    initial: WfState = {
        "task_id": task.id,
        "user_id": user.id,
        "task_type": task.task_type,
        "trace": [],
    }
    result = graph.invoke(initial)
    return str(result.get("final", "")), list(result.get("trace", []))
