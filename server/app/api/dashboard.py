# -*- coding: utf-8 -*-
"""数据看板：企业价值指标聚合统计（SQLite 直查，不引入重型依赖）。"""
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import Integer, func
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.core.response import ok
from app.models import AgentTask, Conversation, ConversationMsg, Department, Document, OperationLog, Team, User

router = APIRouter(prefix="/api/dashboard", tags=["数据看板"])


def _day_series(days: int) -> list[str]:
    """返回 [days-1 .. 0] 的 YYYY-MM-DD 日期序列（今天为最后一天）。"""
    today = date.today()
    return [(today - timedelta(days=d)).isoformat() for d in range(days - 1, -1, -1)]


def _daily_trend(db: Session, days: int) -> dict[str, list]:
    """近 N 日趋势，输出前端折线图可直接消费的平行数组结构。"""
    series = _day_series(days)
    start = datetime.combine(date.today() - timedelta(days=days - 1), datetime.min.time())
    day = func.date

    def counts(query_rows) -> list[int]:
        rows = {str(k): int(v) for k, v in query_rows}
        return [rows.get(d, 0) for d in series]

    docs = counts(db.query(day(Document.create_time), func.count()).filter(Document.is_deleted.is_(False), Document.create_time >= start).group_by(day(Document.create_time)).all())
    chats = counts(db.query(day(ConversationMsg.create_time), func.count()).filter(ConversationMsg.create_time >= start).group_by(day(ConversationMsg.create_time)).all())
    agents = counts(db.query(day(AgentTask.create_time), func.count()).filter(AgentTask.create_time >= start).group_by(day(AgentTask.create_time)).all())
    retrievals = counts(db.query(day(OperationLog.create_time), func.count()).filter(OperationLog.module == "chat", OperationLog.create_time >= start).group_by(day(OperationLog.create_time)).all())
    return {
        "documents": docs,
        "conversations": chats,
        "agents": agents,
        "retrievals": retrievals,
        "dates": series,
    }


# ===== 逐行注释：智能数据看板路由层 =====
# 1. 全部为只读聚合查询（SQLite 直接 group_by/count），不引入重型 BI 依赖；
# 2. _day_series/_daily_trend：生成近 N 日日期序列并统计 文档/对话/Agent/检索 四类
#    指标趋势（平行数组结构，前端折线图可直接消费）；
# 3. /summary：企业价值总览——文档（总数/今日/本周/各状态）、检索（次数/成功率）、
#    对话、Agent（总数/完成/运行/失败/类型分布）、组织（用户/部门/团队）+ 7 日趋势；
# 4. /knowledge-hot：知识热度榜，按 检索次数×2+浏览量 加权排序取 Top10（智能看板"热榜"）；
# 5. /dept-activity：部门活跃度，近 7 日按部门统计 文档新增/对话消息/检索量 后排序取 Top12；
# 6. /retrieval-heatmap：检索热力图，近 14 日每日检索量 + max 用于前端归一化配色；
# 7. /llm-usage：AI 用量报表，近 14 日 LLM 调用次数/成功率/平均耗时趋势 + 按模型汇总。
@router.get("/summary")
def dashboard_summary(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    today_start = datetime.combine(date.today(), datetime.min.time())
    week_start = datetime.combine(date.today() - timedelta(days=date.today().weekday()), datetime.min.time())

    def count_docs(cond) -> int:
        return db.query(func.count(Document.id)).filter(Document.is_deleted.is_(False), cond).scalar() or 0

    doc_total = count_docs(True)
    doc_today = count_docs(Document.create_time >= today_start)
    doc_this_week = count_docs(Document.create_time >= week_start)
    doc_pending = count_docs(Document.status == "pending")
    doc_processing = count_docs(Document.status == "processing")
    doc_ready = count_docs(Document.status == "ready")
    doc_failed = count_docs(Document.status == "failed")

    retrieval_total = db.query(func.count(OperationLog.id)).filter(OperationLog.module == "chat").scalar() or 0
    retrieval_ok = db.query(func.count(OperationLog.id)).filter(OperationLog.module == "chat", OperationLog.status == "success").scalar() or 0
    retrieval_rate = (retrieval_ok / retrieval_total) if retrieval_total else 1.0

    conversation_count = db.query(func.count(Conversation.id)).scalar() or 0
    chat_message_count = db.query(func.count(ConversationMsg.id)).scalar() or 0
    agent_total = db.query(func.count(AgentTask.id)).scalar() or 0
    # 任务终态为 finished（历史数据存在 done/success），统一口径统计已完成
    agent_done = db.query(func.count(AgentTask.id)).filter(AgentTask.status.in_(["finished", "done", "success"])).scalar() or 0
    agent_running = db.query(func.count(AgentTask.id)).filter(AgentTask.status.in_(["pending", "running", "processing"])).scalar() or 0
    agent_failed = db.query(func.count(AgentTask.id)).filter(AgentTask.status == "failed").scalar() or 0

    user_count = db.query(func.count(User.id)).filter(User.status == "active").scalar() or 0
    dept_count = db.query(func.count(Department.id)).scalar() or 0
    team_count = db.query(func.count(Team.id)).scalar() or 0

    # Agent 任务按类型分布
    agent_by_type = [{"name": k, "value": v} for k, v in db.query(AgentTask.task_type, func.count()).group_by(AgentTask.task_type).all()]

    return ok(
        data={
            "document": {"total": doc_total, "today": doc_today, "this_week": doc_this_week, "pending": doc_pending, "processing": doc_processing, "ready": doc_ready, "failed": doc_failed},
            "retrieval": {"count": retrieval_total, "success_rate": round(retrieval_rate, 4)},
            "conversation": {"count": conversation_count, "messages": chat_message_count},
            "agent": {"total": agent_total, "done": agent_done, "running": agent_running, "finished": agent_done, "failed": agent_failed, "by_type": agent_by_type},
            "organization": {"users": user_count, "departments": dept_count, "teams": team_count},
            "trend_7d": _daily_trend(db, 7),
        }
    )


@router.get("/knowledge-hot")
def knowledge_hot(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """知识热度榜：Top 文档按检索命中 + 浏览量加权排序（智能看板）。"""
    rows = (
        db.query(
            Document.id,
            Document.doc_name,
            Document.file_type,
            Document.view_count,
            Document.retrieve_count,
            Document.update_time,
        )
        .filter(Document.is_deleted.is_(False))
        .order_by(((Document.retrieve_count or 0) * 2 + (Document.view_count or 0)).desc(), Document.update_time.desc())
        .limit(10)
        .all()
    )
    data = []
    for rank, (doc_id, doc_name, file_type, view_count, retrieve_count, update_time) in enumerate(rows, 1):
        heat = (retrieve_count or 0) * 2 + (view_count or 0)
        data.append(
            {
                "rank": rank,
                "doc_id": doc_id,
                "doc_name": doc_name,
                "file_type": file_type,
                "view_count": view_count or 0,
                "retrieve_count": retrieve_count or 0,
                "heat_score": heat,
                "update_time": update_time.isoformat() if update_time else None,
            }
        )
    return ok(data={"list": data, "total": len(data)})


@router.get("/dept-activity")
def dept_activity(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """部门活跃度：近 7 日按部门统计 文档新增 / 对话消息 / 检索量（柱状对比）。"""
    start = datetime.combine(date.today() - timedelta(days=6), datetime.min.time())
    day = func.date
    depts = db.query(Department.id, Department.dept_name).all()
    dept_map = {d_id: d_name for d_id, d_name in depts}

    # 文档数按 Document.dept_id
    docs = db.query(Document.dept_id, func.count()).filter(
        Document.is_deleted.is_(False), Document.create_time >= start
    ).group_by(Document.dept_id).all()
    # 对话消息数：ConversationMsg -> Conversation.user_id -> User.dept_id
    chats = (
        db.query(User.dept_id, func.count())
        .join(Conversation, Conversation.user_id == User.id)
        .join(ConversationMsg, ConversationMsg.conv_id == Conversation.id)
        .filter(ConversationMsg.create_time >= start)
        .group_by(User.dept_id)
        .all()
    )
    # 检索量：审计日志 module=chat
    retrievals = db.query(OperationLog.dept_id, func.count()).filter(
        OperationLog.module == "chat", OperationLog.create_time >= start
    ).group_by(OperationLog.dept_id).all()

    doc_map = {k: int(v) for k, v in docs}
    chat_map = {k: int(v) for k, v in chats}
    ret_map = {k: int(v) for k, v in retrievals}

    data = []
    for d_id, d_name in depts:
        documents = doc_map.get(d_id, 0)
        conversations = chat_map.get(d_id, 0)
        retrievals_n = ret_map.get(d_id, 0)
        total = documents + conversations + retrievals_n
        if total == 0:
            continue
        data.append(
            {
                "dept_id": d_id,
                "dept_name": d_name,
                "documents": documents,
                "conversations": conversations,
                "retrievals": retrievals_n,
                "total": total,
            }
        )
    data.sort(key=lambda x: x["total"], reverse=True)
    return ok(data={"list": data[:12], "days": 7})


@router.get("/retrieval-heatmap")
def retrieval_heatmap(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """检索热力图：近 14 日检索量日历热力数据（智能看板）。"""
    series = _day_series(14)
    start = datetime.combine(date.today() - timedelta(days=13), datetime.min.time())
    day = func.date
    rows = (
        db.query(day(OperationLog.create_time), func.count())
        .filter(OperationLog.module == "chat", OperationLog.create_time >= start)
        .group_by(day(OperationLog.create_time))
        .all()
    )
    count_map = {str(k): int(v) for k, v in rows}
    data = [{"date": d, "count": count_map.get(d, 0)} for d in series]
    max_count = max((x["count"] for x in data), default=0)
    return ok(data={"list": data, "max": max_count, "days": 14})


@router.get("/llm-usage")
def llm_usage(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """AI 用量报表：LLM 调用次数 / 成功率 / 耗时趋势（近 14 日，数据来自 llm_call_log）。"""
    from app.models import LlmCallLog

    days = 14
    series = _day_series(days)
    start = datetime.combine(date.today() - timedelta(days=days - 1), datetime.min.time())
    day = func.date

    rows = (
        db.query(day(LlmCallLog.create_time), func.count(), func.sum(LlmCallLog.is_success.cast(Integer)), func.avg(LlmCallLog.latency_ms))
        .filter(LlmCallLog.create_time >= start)
        .group_by(day(LlmCallLog.create_time))
        .all()
    )
    day_map = {str(k): (int(total), int(success), float(avg or 0)) for k, total, success, avg in rows}

    trend = []
    for d in series:
        total, success, avg_latency = day_map.get(d, (0, 0, 0.0))
        trend.append(
            {
                "date": d,
                "calls": total,
                "success_rate": round(success / total, 4) if total else 1.0,
                "avg_latency_ms": round(avg_latency, 1),
            }
        )

    total_calls = sum(x["calls"] for x in trend)
    # 更精确的成功数统计：按日求和
    total_success = sum(day_map.get(d, (0, 0, 0.0))[1] for d in series)
    avg_all = sum(day_map.get(d, (0, 0, 0.0))[2] for d in series if day_map.get(d, (0, 0, 0.0))[0] > 0)
    latency_count = sum(1 for d in series if day_map.get(d, (0, 0, 0.0))[0] > 0)

    by_model = [
        {
            "model_name": name,
            "calls": int(cnt),
            "success_rate": round(int(suc) / int(cnt), 4) if cnt else 1.0,
            "avg_latency_ms": round(float(avg or 0), 1),
        }
        for name, cnt, suc, avg in db.query(
            LlmCallLog.model_name, func.count(), func.sum(LlmCallLog.is_success.cast(Integer)), func.avg(LlmCallLog.latency_ms)
        )
        .filter(LlmCallLog.create_time >= start)
        .group_by(LlmCallLog.model_name)
        .all()
    ]

    return ok(
        data={
            "days": days,
            "trend": trend,
            "summary": {
                "total_calls": total_calls,
                "success_rate": round(total_success / total_calls, 4) if total_calls else 1.0,
                "avg_latency_ms": round(avg_all / latency_count, 1) if latency_count else 0.0,
                "by_model": by_model,
            },
        }
    )
