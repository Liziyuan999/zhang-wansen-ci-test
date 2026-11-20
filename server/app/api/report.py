# -*- coding: utf-8 -*-
"""AI 周报接口：周期选择 → LangGraph 生成 → 预览/复制/导出。"""
import html as _html
import re
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.code import PARAM_ERROR
from app.core.deps import get_current_user, get_db
from app.core.response import BizError, ok
from app.models import User
from app.services.audit import record_audit
from app.services.weekly_report_service import TEMPLATE_SECTIONS, run_weekly_report

router = APIRouter(prefix="/api/report", tags=["AI 周报"])

SECTION_DESC = {
    "overview": "本周整体运营概览：文档、对话、检索、Agent 等核心指标摘要",
    "knowledge": "知识资产新增/状态分布，沉淀与质量情况",
    "chat": "对话与检索活跃度，知识调用情况",
    "agent": "Agent 任务执行情况：总量、成功/失败与类型分布",
    "organization": "组织规模变化：用户、部门、团队协作情况",
    "next": "基于数据给出下周行动建议与关注点",
}

_PERIOD_LABEL = {"week": "本周", "last_week": "上周", "7d": "近 7 天", "custom": "自定义"}


def _md_to_html_safe(markdown: str) -> str:
    """Markdown → HTML（先 HTML 转义，杜绝 LLM 输出注入脚本）。"""
    lines = markdown.splitlines()
    out: list[str] = []
    in_list = False
    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            if in_list:
                out.append("</ul>")
                in_list = False
            continue
        escaped = _html.escape(line)
        m = re.match(r"^(#{1,6})\s+(.*)$", escaped)
        if m:
            if in_list:
                out.append("</ul>")
                in_list = False
            level = min(len(m.group(1)) + 1, 6)
            out.append(f"<h{level}>{m.group(2)}</h{level}>")
            continue
        m = re.match(r"^\s*[-*]\s+(.*)$", escaped)
        if m:
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{m.group(1)}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        # 行内粗体（已转义，仅处理 ** 标记）
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
        out.append(f"<p>{text}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


class WeeklyReportReq(BaseModel):
    start_date: str = ""
    end_date: str = ""
    period: str = "week"  # week | last_week | 7d | custom
    focus: str = ""
    model_provider_id: int | None = None  # 指定模型供应商；不传则使用默认供应商/环境变量


def _resolve_period(period: str, start_date: str, end_date: str) -> tuple[str, str]:
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    if period == "last_week":
        return (monday - timedelta(days=7)).isoformat(), (monday - timedelta(days=1)).isoformat()
    if period == "7d":
        return (today - timedelta(days=6)).isoformat(), today.isoformat()
    if period == "custom":
        if not start_date or not end_date:
            raise BizError(PARAM_ERROR, "自定义周期需提供 start_date 与 end_date")
        return start_date, end_date
    return monday.isoformat(), today.isoformat()


@router.get("/template")
def get_template(_: User = Depends(get_current_user)):
    return ok(
        data={
            "title": "知寻 KnowSeek 企业周报模板",
            "summary": "按固定章节生成结构化企业周报，LangGraph 三节点工作流（数据聚合 → LLM 生成 → 质检修订）",
            "sections": [{"key": s["key"], "title": s["title"], "desc": SECTION_DESC.get(s["key"], "")} for s in TEMPLATE_SECTIONS],
            "periods": [{"value": "week", "label": "本周"}, {"value": "last_week", "label": "上周"}, {"value": "7d", "label": "近 7 天"}, {"value": "custom", "label": "自定义"}],
        }
    )


@router.post("/weekly")
def generate_weekly(req: WeeklyReportReq, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    start_date, end_date = _resolve_period(req.period, req.start_date, req.end_date)
    try:
        markdown, trace, fallback = run_weekly_report(db, user, start_date, end_date, req.focus)
    except Exception as exc:  # noqa: BLE001
        raise BizError(PARAM_ERROR, f"周报生成失败：{exc}") from exc
    record_audit(db, user, "weekly", "report", detail=f"生成周报 {start_date} ~ {end_date}", ip="")
    period_label = f"{_PERIOD_LABEL.get(req.period, '本周')}（{start_date} ~ {end_date}）"
    return ok(
        data={
            "markdown": markdown,
            "html": _md_to_html_safe(markdown),
            "period_label": period_label,
            "start_date": start_date,
            "end_date": end_date,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "template" if fallback else "llm",
            "trace": trace,
        }
    )
