# -*- coding: utf-8 -*-
"""Agent 任务服务：周报/文档对比/方案撰写，检索后需人工确认。"""
import json
import logging
from collections import deque
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.code import NOT_FOUND, PARAM_ERROR, SENSITIVE_CONTENT, TASK_STATE_NOT_ALLOWED
from app.core.config import settings
from app.core.response import BizError
from app.core.sensitive import DEFENSIVE_SYSTEM_HINT, contains_injection, contains_sensitive, guard_user_content
from app.models import AgentTask, AgentTemplate, DocChunk, Document, User, UserNotification
from app.services.llm import chat_completion
from app.services.vector_store import VectorStoreRepository
from app.services.web_search import search_web

logger = logging.getLogger(__name__)

_vector_store = VectorStoreRepository()

TASK_PROMPTS = {
    "weekly_report": "请基于以下知识片段，撰写一份结构清晰的企业周报，包含：本周重点工作、关键成果、问题与风险、下周计划。",
    "doc_compare": "请基于以下知识片段，对所选文档进行对比分析，包含：核心差异点、共同点、各自的优劣势、结论建议。",
    "write_plan": "请基于以下知识片段，撰写一份可执行的方案，包含：背景目标、方案设计、实施步骤、资源与风险、时间计划。",
}

DEFAULT_QUERIES = {
    "weekly_report": ["本周工作总结 重点成果 风险 计划"],
    "doc_compare": ["对比 差异 共同点 优势 结论"],
    "write_plan": ["方案 目标 实施步骤 资源 风险 计划"],
}

# 拖拽画布支持的工作流节点类型（与 canvas_workflow.NODE_TYPES 保持一致）
CANVAS_NODE_TYPES = {"input", "plan", "retrieve", "generate", "reflect", "refine", "output"}


def validate_canvas_json(canvas_json: str | None) -> None:
    """创建任务/保存模板时前置校验画布结构。

    修复点：此前非法 canvas_json 或未知节点类型要等到任务执行期才报 failed，
    前端只能看到"任务失败"；改为创建期即返回参数错误（10001），快速失败。
    """
    if not canvas_json:
        return
    try:
        canvas = json.loads(canvas_json)
    except Exception:  # noqa: BLE001
        raise BizError(PARAM_ERROR, "画布 JSON 格式不合法，请检查后重试") from None
    if not isinstance(canvas, dict):
        raise BizError(PARAM_ERROR, "画布结构必须为对象（需包含 nodes / edges）")
    nodes = canvas.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise BizError(PARAM_ERROR, "画布至少需要 1 个节点")
    seen: set[str] = set()
    for n in nodes:
        if not isinstance(n, dict):
            raise BizError(PARAM_ERROR, "画布节点格式不合法")
        nid = str(n.get("id") or "")
        ntype = n.get("type")
        if not nid:
            raise BizError(PARAM_ERROR, "画布节点缺少 id")
        if nid in seen:
            raise BizError(PARAM_ERROR, f"画布节点 id 重复：{nid}")
        seen.add(nid)
        if ntype not in CANVAS_NODE_TYPES:
            raise BizError(PARAM_ERROR, f"不支持的节点类型：{ntype}")
    edges = canvas.get("edges") or []
    if not isinstance(edges, list):
        raise BizError(PARAM_ERROR, "画布 edges 必须为数组")
    for e in edges:
        if not isinstance(e, dict):
            raise BizError(PARAM_ERROR, "画布连线格式不合法")
        for k in ("source", "target"):
            if str(e.get(k) or "") not in seen:
                raise BizError(PARAM_ERROR, f"画布连线指向不存在的节点：{e.get(k)}")
    # 修复 P2：新增成环检测。原实现只校验节点/连线合法性，环状工作流要到执行期才报错甚至递归超限。
    # 用 Kahn 拓扑排序判定有向无环图：能全部出队说明无环，否则存在循环依赖。
    in_degree: dict[str, int] = {nid: 0 for nid in seen}
    out_edges: dict[str, list[str]] = {nid: [] for nid in seen}
    for e in edges:
        src, dst = str(e.get("source") or ""), str(e.get("target") or "")
        if src == dst:
            raise BizError(PARAM_ERROR, f"画布连线不能指向节点自身：{src}")
        out_edges[src].append(dst)
        in_degree[dst] += 1
    queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
    visited = 0
    while queue:
        cur = queue.popleft()
        visited += 1
        for nxt in out_edges[cur]:
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                queue.append(nxt)
    if visited != len(seen):
        raise BizError(PARAM_ERROR, "画布存在循环依赖（连线成环），请调整节点连线后重试")


def build_context_text(chunks: list[dict[str, Any]], web_sources: list[dict[str, Any]] | None = None, doc_map: dict[int, str] | None = None) -> str:
    """将检索片段与联网来源构造成可注入 LLM 的上下文文本（供经典生成与 LangGraph 工作流共用）。"""
    doc_map = doc_map or {}
    context_parts = []
    for i, c in enumerate(chunks, 1):
        src = doc_map.get(c["doc_id"], f"文档{c['doc_id']}")
        if c.get("page_no"):
            src += f" 第{c['page_no']}页"
        context_parts.append(f"[{i}] {src}\n{c['text']}")
    context = "\n\n".join(context_parts) or "（未检索到相关内容）"
    web_context_parts = []
    for i, w in enumerate(web_sources or [], 1):
        web_context_parts.append(f"[W{i}] 标题:{w.get('title', '')}\n来源:{w.get('url', '')}\n摘要:{w.get('snippet', '')}")
    web_context = "\n\n".join(web_context_parts)
    if web_context:
        context += "\n\n网络搜索结果：\n" + web_context
    return context


def _ensure_params_column(db: Session) -> None:
    """老库兼容：agent_task 表无 params 列时补充（SQLite 原生 ALTER ADD COLUMN）。"""
    try:
        cols = [row[1] for row in db.execute(text("PRAGMA table_info(agent_task)")).fetchall()]
        if "params" not in cols:
            db.execute(text("ALTER TABLE agent_task ADD COLUMN params JSON"))
            db.commit()
    except Exception as exc:  # pragma: no cover
        logger.warning("补充 agent_task.params 列失败（不影响主流程）: %s", exc)
        db.rollback()


def _ensure_web_sources_column(db: Session) -> None:
    """老库兼容：agent_task 表无 web_sources 列时补充（SQLite 原生 ALTER ADD COLUMN）。"""
    try:
        cols = [row[1] for row in db.execute(text("PRAGMA table_info(agent_task)")).fetchall()]
        if "web_sources" not in cols:
            db.execute(text("ALTER TABLE agent_task ADD COLUMN web_sources JSON"))
            db.commit()
    except Exception as exc:  # pragma: no cover
        logger.warning("补充 agent_task.web_sources 列失败（不影响主流程）: %s", exc)
        db.rollback()


def _ensure_workflow_trace_column(db: Session) -> None:
    """老库兼容：agent_task 表无 workflow_trace 列时补充（LangGraph 工作流轨迹）。"""
    try:
        cols = [row[1] for row in db.execute(text("PRAGMA table_info(agent_task)")).fetchall()]
        if "workflow_trace" not in cols:
            db.execute(text("ALTER TABLE agent_task ADD COLUMN workflow_trace JSON"))
            db.commit()
    except Exception as exc:  # pragma: no cover
        logger.warning("补充 agent_task.workflow_trace 列失败（不影响主流程）: %s", exc)
        db.rollback()


def _retrieve_for_task(
    db: Session, user: User, task_type: str, doc_ids: list[int], vector_store: VectorStoreRepository
) -> list[dict[str, Any]]:
    # P1-8：原实现把本部门全部可用文档整表加载进内存做存活判断，文档量增长后内存与耗时不可控。
    # 改为：指定文档时仅按 id 集合 IN 查询校验；未指定时延迟到拿到向量候选后，只校验候选 doc_id。
    seed_ids = [int(x) for x in (doc_ids or [])]
    # 修复 P0-1：原写法仅做类型注解未赋初值，doc_ids 为空时 available 未定义，
    # 下方 "if available is None" 会抛 UnboundLocalError，导致任务创建即 failed。
    available: set[int] | None = None
    if seed_ids:
        rows = (
            db.query(Document.id)
            .filter(
                Document.id.in_(seed_ids),
                Document.dept_id == user.dept_id,
                Document.is_deleted.is_(False),
                Document.status == "success",
            )
            .all()
        )
        available = {r[0] for r in rows}
        for did in seed_ids:
            if did not in available:
                raise BizError(NOT_FOUND, f"文档 {did} 不存在或不可访问")

    query_map = {
        "weekly_report": "本周工作总结 重点成果 风险 计划",
        "doc_compare": "对比 差异 共同点 优势 结论",
        "write_plan": "方案 目标 实施步骤 资源 风险 计划",
    }
    query_text = query_map.get(task_type, "知识检索")
    candidates = vector_store.query(query_text, dept_id=user.dept_id, top_k=settings.RAG_TOP_K * 2)
    # P1-6 软删过滤：向量库仅按部门过滤，会命中回收站文档切片；
    # P1-7：未指定文档时只对"候选 doc_id"做一次 IN 存活校验，不再全表加载文档。
    if available is None:
        cand_ids = {c["doc_id"] for c in candidates}
        available = (
            {
                r[0]
                for r in db.query(Document.id)
                .filter(
                    Document.id.in_(cand_ids),
                    Document.dept_id == user.dept_id,
                    Document.is_deleted.is_(False),
                    Document.status == "success",
                )
                .all()
            }
            if cand_ids
            else set()
        )
    candidates = [c for c in candidates if c["doc_id"] in available]

    if doc_ids:
        candidates = [c for c in candidates if c["doc_id"] in set(doc_ids)]
        if len(candidates) < settings.RAG_TOP_K:
            # 检索不足时，直接从指定文档补充最新切片，保证任务有足够上下文
            need = settings.RAG_TOP_K - len(candidates)
            # P1-7：原实现按 doc_id 逐个查 DocChunk（N+1），改为一次 IN 查询后在内存按文档分桶
            rows = (
                db.query(DocChunk)
                .filter(DocChunk.doc_id.in_(doc_ids))
                .order_by(DocChunk.doc_id.asc(), DocChunk.id.asc())
                .limit(need * max(1, len(doc_ids)))
                .all()
            )
            bucket: dict[int, list] = {}
            for r in rows:
                bucket.setdefault(r.doc_id, []).append(r)
            supplement: list[dict[str, Any]] = []
            for did in doc_ids:
                if len(supplement) >= need:
                    break
                for r in bucket.get(did, [])[:need]:
                    supplement.append(
                        {
                            "chunk_id": r.chroma_id,
                            "doc_id": r.doc_id,
                            "text": r.chunk_text,
                            "page_no": r.page_no,
                            "sheet_name": r.sheet_name,
                            "score": 1.0,
                        }
                    )
                    if len(supplement) >= need:
                        break
            candidates = (candidates + supplement)[: settings.RAG_TOP_K]
    return candidates[: settings.RAG_TOP_K]


def create_agent_task(
    db: Session,
    user: User,
    task_type: str,
    doc_ids: list[int],
    params: dict[str, Any],
    vector_store: VectorStoreRepository,
    provider_id: int | None = None,
    schedule_type: str = "once",
    schedule_cron: str | None = None,
    template_id: int | None = None,
    notify_on_finish: bool = True,
    canvas_json: str | None = None,
) -> AgentTask:
    # ===== 逐行注释：Agent 任务创建（核心）=====
    # 1. 参数安全防线：把用户补充参数序列化为文本，先过敏感词（contains_sensitive）
    #    与提示注入（contains_injection）双校验，不合格直接拒绝创建；
    # 2. 老库兼容：通过 _ensure_*_column 为旧 SQLite 表补充缺失列（params/web_sources/workflow_trace）；
    # 3. 创建 AgentTask 记录，初始 status=retrieving（先检索、后确认、再生成）；
    # 4. _retrieve_for_task() 做部门级 RAG 检索：仅取本部门未删除且解析成功的文档，
    #    指定 doc_ids 时校验可访问性，检索不足会从指定文档最新切片补足上下文；
    # 5. 可选联网检索：params.web_search=True 时融合实时网络结果（失败兜底为空，不影响主流程）；
    # 6. 状态分流：once 任务置 waiting_confirm 等人工确认（安全机制）；周期任务
    #    （daily/weekly）直接 finished 并立即 _build_result 生成结果；
    # 7. 任何异常都会落 failed 状态 + error_msg，保证前端可观测。
    params = dict(params or {})
    # 画布结构前置校验（快速失败，避免执行期才 failed）
    validate_canvas_json(canvas_json)
    if provider_id is not None:
        params["model_provider_id"] = provider_id
    # 补充参数安全校验：敏感词直接拒绝，注入文本拒绝（不进入任务 prompt）
    param_text = json.dumps(params, ensure_ascii=False) if params else ""
    if contains_sensitive(param_text):
        raise BizError(SENSITIVE_CONTENT, "任务补充参数包含敏感词，请修改后重试")
    if contains_injection(param_text):
        raise BizError(SENSITIVE_CONTENT, "任务补充参数包含提示注入内容，已拒绝创建")

    _ensure_params_column(db)
    _ensure_web_sources_column(db)
    task = AgentTask(
        user_id=user.id,
        task_type=task_type,
        selected_doc_ids=doc_ids or None,
        params=params or None,
        status="retrieving",
        template_id=template_id,
        schedule_type=schedule_type,
        schedule_cron=schedule_cron,
        notify_on_finish=notify_on_finish,
        canvas_json=canvas_json,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    try:
        chunks = _retrieve_for_task(db, user, task_type, doc_ids, vector_store)
        task.retrieval_chunks = chunks
        # 联网检索开关：参数 params.web_search=True 时融合实时网络结果（默认关，失败兜底为空）
        web_sources: list[dict[str, Any]] = []
        if (params or {}).get("web_search"):
            query_map = {
                "weekly_report": "本周工作总结 重点成果 风险 计划",
                "doc_compare": "对比 差异 共同点 优势 结论",
                "write_plan": "方案 目标 实施步骤 资源 风险 计划",
            }
            try:
                web_sources = search_web(query_map.get(task_type, "知识检索"))
            except Exception:  # noqa: BLE001
                web_sources = []
        task.web_sources = web_sources or None
        # 周期任务自动执行（无需人工确认），一次性任务等待确认
        task.status = "waiting_confirm" if schedule_type == "once" else "finished"
        if task.status == "finished":
            _t0 = datetime.now()
            task.task_result = _build_result(db, user, task)
            task.finish_time = datetime.now()
            _ensure_workflow_trace_column(db)
            task.workflow_trace = _build_task_trace(
                task, int((datetime.now() - _t0).total_seconds() * 1000))
        db.commit()
        db.refresh(task)
        return task
    except BizError as exc:
        # 修复 P0-1 配套：业务校验类错误（如文档不存在/不可访问）此前被 except Exception 吞掉，
        # 任务落 failed 但接口仍返回"创建成功"，前端表现为"成功但任务失败"。
        # 现在先落 failed 便于审计，再把业务错误抛给接口层，由统一响应返回 10001/10004 与明确原因。
        db.rollback()
        task.status = "failed"
        task.error_msg = str(exc)
        db.commit()
        db.refresh(task)
        raise
    except Exception as exc:  # pragma: no cover
        db.rollback()
        task.status = "failed"
        task.error_msg = str(exc)
        db.commit()
        db.refresh(task)
        return task


def _build_result(db: Session, user: User, task: AgentTask) -> str:
    chunks = task.retrieval_chunks or []
    doc_ids = list({c["doc_id"] for c in chunks})
    doc_map: dict[int, str] = {}
    if doc_ids:
        # P1-6 软删过滤：仅取未删除文档名作为引用标题
        rows = db.query(Document).filter(Document.id.in_(doc_ids), Document.is_deleted.is_(False)).all()
        doc_map = {d.id: d.doc_name for d in rows}

    context = build_context_text(chunks, task.web_sources or [], doc_map)
    prompt = TASK_PROMPTS.get(task.task_type, "请根据以下内容生成结果")
    # 用户补充参数作为数据注入任务要求，并做注入防御包装
    extra = (task.params or {}).get("extra")
    if extra:
        prompt = f"{prompt}\n\n用户补充要求：{guard_user_content(str(extra))}"
    system = (
        "你是「知寻 KnowSeek」企业智能 Agent。请严格基于知识片段生成结果，并正确标注引用来源。"
        + ("同时提供实时网络搜索结果（编号 [W1] [W2] 等），可结合网络信息补充，使用网络来源时以 [W1] 等角标标注。"
        if (task.web_sources or []) else "")
        + "\n\n知识片段：\n"
        + context
        + "\n\n"
        + DEFENSIVE_SYSTEM_HINT
    )
    messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    provider_id = (task.params or {}).get("model_provider_id")
    return chat_completion(db, user.id, messages, scenario=f"agent_{task.task_type}", provider_id=provider_id)


def _build_task_trace(task: AgentTask, cost_ms: int = 0) -> list[dict[str, Any]]:
    """普通 Agent 任务的基础执行轨迹（检索 → 规划 → 生成 → 输出）。

    修复点：此前仅画布任务与 LangGraph 任务写入 workflow_trace，
    三类模板任务（weekly_report / doc_compare / write_plan）及周期任务
    的 workflow_trace 恒为 None，前端任务详情页「执行轨迹」面板始终空白。
    """
    chunks = task.retrieval_chunks or []
    doc_ids = sorted({c.get("doc_id") for c in chunks if c.get("doc_id")})
    web = task.web_sources or []
    result_len = len(task.task_result or "")
    finish_at = task.finish_time.strftime("%Y-%m-%d %H:%M:%S") if task.finish_time else ""
    retrieve_summary = f"命中 {len(chunks)} 个知识片段，覆盖 {len(doc_ids)} 篇文档"
    if web:
        retrieve_summary += f"；联网来源 {len(web)} 条"
    return [
        {"node": "retrieve", "name": "知识检索", "status": "success",
         "summary": retrieve_summary, "cost_ms": 0},
        {"node": "plan", "name": "任务规划", "status": "success",
         "summary": f"任务类型 {task.task_type}，按模板提示词与防御性指令组装请求", "cost_ms": 0},
        {"node": "generate", "name": "结果生成", "status": "success",
         "summary": f"生成结果 {result_len} 字", "cost_ms": cost_ms},
        {"node": "output", "name": "结果输出", "status": "success",
         "summary": f"完成于 {finish_at}" if finish_at else "结果已输出", "cost_ms": 0},
    ]


def confirm_task(db: Session, user: User, task_id: int, confirm: bool) -> AgentTask:
    task = db.get(AgentTask, task_id)
    if not task or task.user_id != user.id:
        raise BizError(NOT_FOUND, "任务不存在")
    if task.status != "waiting_confirm":
        raise BizError(TASK_STATE_NOT_ALLOWED, f"任务状态不允许确认（当前 {task.status}）")
    if confirm:
        try:
            # 画布执行判定：显式指定 canvas，或已携带 canvas_json 且非 langgraph（避免仅传画布时静默降级为普通任务）
            if task.canvas_json and (task.params or {}).get("graph_engine") != "langgraph":
                # 拖拽式工作流编排：按画布连线顺序执行节点
                from app.services.canvas_workflow import run_canvas_workflow

                _ensure_workflow_trace_column(db)
                provider_id = (task.params or {}).get("model_provider_id")
                result, trace = run_canvas_workflow(db, user, task, provider_id=provider_id)
                task.task_result = result
                task.workflow_trace = trace
            elif (task.params or {}).get("graph_engine") == "langgraph":
                # LangGraph 多节点工作流编排：规划→检索→生成→反思→精修
                from app.services.langgraph_workflow import run_langgraph_workflow

                _ensure_workflow_trace_column(db)
                provider_id = (task.params or {}).get("model_provider_id")
                result, trace = run_langgraph_workflow(db, user, task, _vector_store, provider_id=provider_id)
                task.task_result = result
                task.workflow_trace = trace
            else:
                _t0 = datetime.now()
                task.task_result = _build_result(db, user, task)
                _ensure_workflow_trace_column(db)
                task.workflow_trace = _build_task_trace(
                    task, int((datetime.now() - _t0).total_seconds() * 1000))
            task.status = "finished"
        except Exception as exc:  # pragma: no cover
            task.status = "failed"
            task.error_msg = str(exc)
    else:
        task.status = "cancelled"
    task.finish_time = datetime.now()
    db.commit()
    db.refresh(task)
    _notify_task_finished(db, task)
    return task


def _notify_task_finished(db: Session, task: AgentTask) -> None:
    """Agent 任务完成通知（通知中心闭环）：完成后写入全局用户通知。"""
    if not task.notify_on_finish or task.notified:
        return
    if task.status not in ("finished", "failed"):
        return
    task.notified = True
    type_name = {"weekly_report": "周报生成", "doc_compare": "文档对比", "write_plan": "方案撰写"}.get(task.task_type, "Agent 任务")
    if task.status == "finished":
        title = f"{type_name}任务已完成"
        content = f"您的「{type_name}」任务已完成，可在 Agent 任务中心查看结果。"
    else:
        title = f"{type_name}任务执行失败"
        content = f"您的「{type_name}」任务执行失败：{task.error_msg or '未知错误'}，请调整后重试。"
    db.add(
        UserNotification(
            user_id=task.user_id,
            title=title,
            content=content,
            ntype="agent",
            related_id=task.id,
        )
    )
    db.commit()


def list_tasks(db: Session, user: User, page: int | None = None, page_size: int | None = None) -> tuple[list[AgentTask], int]:
    """智能体任务列表。

    P1-8：原实现一次性拉取用户全部任务（无上限），现支持 page/page_size 分页并返回真实总数；
    page 为 None 时保持旧行为（一次返回全部），供内部调用方兼容。
    """
    q = db.query(AgentTask).filter(AgentTask.user_id == user.id)
    total = q.count() if page is not None else 0
    q = q.order_by(AgentTask.create_time.desc(), AgentTask.id.desc())
    if page is not None:
        q = q.offset((page - 1) * page_size).limit(page_size)
    rows = q.all()
    return rows, (total if page is not None else len(rows))


def get_task(db: Session, user: User, task_id: int) -> AgentTask:
    task = db.get(AgentTask, task_id)
    if not task or task.user_id != user.id:
        raise BizError(NOT_FOUND, "任务不存在")
    return task


# ---------- 任务模板 ----------

def create_template(db: Session, user: User, payload: dict[str, Any]) -> AgentTemplate:
    validate_canvas_json(payload.get("canvas_json"))
    tpl = AgentTemplate(
        user_id=user.id,
        template_name=payload["template_name"],
        task_type=payload["task_type"],
        selected_doc_ids=payload.get("doc_ids") or None,
        params=payload.get("params") or None,
        schedule_type=payload.get("schedule_type", "once"),
        schedule_cron=payload.get("schedule_cron"),
        notify_on_finish=payload.get("notify_on_finish", True),
        canvas_json=payload.get("canvas_json"),
    )
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    return tpl


def update_template(db: Session, user: User, template_id: int, payload: dict[str, Any]) -> AgentTemplate:
    tpl = db.get(AgentTemplate, template_id)
    if not tpl or tpl.user_id != user.id:
        raise BizError(NOT_FOUND, "模板不存在")
    if "canvas_json" in payload:
        validate_canvas_json(payload.get("canvas_json"))
    for key in (
        "template_name",
        "task_type",
        "doc_ids",
        "params",
        "schedule_type",
        "schedule_cron",
        "notify_on_finish",
        "canvas_json",
    ):
        if key in payload:
            setattr(tpl, key, payload[key])
    db.commit()
    db.refresh(tpl)
    return tpl


def list_templates(db: Session, user: User) -> list[AgentTemplate]:
    return (
        db.query(AgentTemplate)
        .filter(AgentTemplate.user_id == user.id)
        .order_by(AgentTemplate.create_time.desc())
        .all()
    )


def delete_template(db: Session, user: User, template_id: int) -> None:
    tpl = db.get(AgentTemplate, template_id)
    if not tpl or tpl.user_id != user.id:
        raise BizError(NOT_FOUND, "模板不存在")
    db.delete(tpl)
    db.commit()


def template_to_task(db: Session, user: User, template_id: int) -> AgentTask:
    """从模板创建任务：周期模板创建周期任务并立即执行一次。"""
    tpl = db.get(AgentTemplate, template_id)
    if not tpl or tpl.user_id != user.id:
        raise BizError(NOT_FOUND, "模板不存在")
    params = dict(tpl.params or {})
    # 模板含画布 JSON 时强制走画布工作流引擎，保证运行链路按 nodes/edges 执行
    if tpl.canvas_json:
        params["graph_engine"] = "canvas"
    return create_agent_task(
        db,
        user,
        tpl.task_type,
        tpl.selected_doc_ids or [],
        params,
        _vector_store,
        provider_id=params.get("model_provider_id"),
        schedule_type=tpl.schedule_type,
        schedule_cron=tpl.schedule_cron,
        template_id=tpl.id,
        notify_on_finish=tpl.notify_on_finish,
        canvas_json=tpl.canvas_json,
    )


# ---------- 周期任务扫描 ----------

def _parse_cron(cron: str | None) -> tuple[int, int, int] | None:
    """解析 "M H * * W" 或 "M H * * *"，返回 (minute, hour, weekday)；weekday -1 表示每天。"""
    if not cron:
        return None
    parts = cron.split()
    if len(parts) < 5:
        return None
    try:
        minute = int(parts[0])
        hour = int(parts[1])
        wd = parts[4]
        weekday = -1 if wd == "*" else int(wd) % 7  # 兼容 1-7 与 0-6
        return minute, hour, weekday
    except (TypeError, ValueError):
        return None


def run_scheduled_tasks() -> int:
    """扫描周期 Agent 任务，到点自动执行一次并通知（由后台调度器周期调用）。"""
    from app.db.session import SessionLocal

    db = SessionLocal()
    executed = 0
    try:
        now = datetime.now()
        tasks = (
            db.query(AgentTask)
            .filter(AgentTask.schedule_type.in_(["daily", "weekly"]), AgentTask.status.in_(["finished", "failed"]))
            .all()
        )
        # P1-7：原实现按到期任务逐条 db.get(User)，改为一次 IN 预加载任务归属用户
        owner_ids = {t.user_id for t in tasks if t.user_id is not None}
        user_map = (
            {u.id: u for u in db.query(User).filter(User.id.in_(owner_ids)).all()} if owner_ids else {}
        )
        for task in tasks:
            parsed = _parse_cron(task.schedule_cron)
            if not parsed:
                continue
            minute, hour, weekday = parsed
            if now.hour != hour or now.minute != minute:
                continue
            if weekday != -1 and now.weekday() != weekday:
                continue
            # 当日/本周已执行过则跳过
            if task.finish_time and (
                task.finish_time.date() == now.date()
                or (weekday != -1 and task.finish_time.isocalendar().week == now.isocalendar().week)
            ):
                continue
            user = user_map.get(task.user_id)
            if not user:
                continue
            try:
                task.retrieval_chunks = _retrieve_for_task(db, user, task.task_type, task.selected_doc_ids or [], _vector_store)
                task.task_result = _build_result(db, user, task)
                task.status = "finished"
                task.error_msg = None
            except Exception as exc:  # noqa: BLE001
                task.status = "failed"
                task.error_msg = str(exc)
            task.finish_time = datetime.now()
            db.commit()
            db.refresh(task)
            _notify_task_finished(db, task)
            executed += 1
    except Exception:  # noqa: BLE001
        logger.exception("周期任务扫描执行失败")
    finally:
        db.close()
    return executed
