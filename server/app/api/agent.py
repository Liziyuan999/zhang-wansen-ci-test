# -*- coding: utf-8 -*-
"""Agent 任务接口：创建/确认/列表/详情/模板。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.response import ok
from app.models import User
from app.schemas.agent import AgentConfirmReq, AgentTaskReq, AgentTaskResp, AgentTemplateReq, AgentTemplateResp
from app.services import agent_service
from app.services.vector_store import VectorStoreRepository

router = APIRouter(prefix="/api/agent", tags=["Agent"])
vector_store = VectorStoreRepository()


def _task_resp(task) -> dict:
    return AgentTaskResp(
        task_id=task.id,
        task_type=task.task_type,
        status=task.status,
        need_confirm=task.status == "waiting_confirm",
        selected_doc_ids=task.selected_doc_ids,
        params=task.params,
        retrieval_chunks=task.retrieval_chunks or [],
        web_sources=task.web_sources,
        workflow_trace=task.workflow_trace,
        task_result=task.task_result,
        create_time=task.create_time.strftime("%Y-%m-%d %H:%M:%S") if task.create_time else None,
        finish_time=task.finish_time.strftime("%Y-%m-%d %H:%M:%S") if task.finish_time else None,
        error_msg=task.error_msg,
        schedule_type=task.schedule_type,
        schedule_cron=task.schedule_cron,
        template_id=task.template_id,
        notify_on_finish=task.notify_on_finish,
        canvas_json=task.canvas_json,
    ).model_dump(mode="json")


# ===== 逐行注释：Agent 任务路由层 =====
# 1. 统一前缀 /api/agent，vector_store 为全局向量库仓储，供创建任务时注入检索能力；
# 2. _task_resp 把 ORM 任务对象转为前端友好的 JSON（含 need_confirm 标志、
#    retrieval_chunks 检索引用、workflow_trace 画布执行轨迹、canvas_json 画布定义等）；
# 3. POST /tasks：创建任务，once 任务进入 waiting_confirm 等人工确认，周期任务立即执行首次运行；
# 4. POST /tasks/{id}/confirm：人工确认/取消执行，是"人工介入"安全机制的关键节点；
# 5. GET /tasks 与 GET /tasks/{id}：任务列表与详情（前端轮询查看状态）；
# 6. 模板体系：POST/GET/DELETE/PUT /templates 管理可复用任务模板；
#    POST /templates/{id}/run 按模板创建任务并跳过人工确认直接执行（模板视为已授权）。
@router.post("/tasks")
def create_task(req: AgentTaskReq, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = agent_service.create_agent_task(
        db,
        user,
        req.task_type,
        req.doc_ids,
        req.params,
        vector_store,
        provider_id=req.model_provider_id,
        schedule_type=req.schedule_type,
        schedule_cron=req.schedule_cron,
        template_id=req.template_id,
        notify_on_finish=req.notify_on_finish,
        canvas_json=req.canvas_json,
    )
    return ok(data=_task_resp(task), message="任务已创建，等待人工确认" if req.schedule_type == "once" else "周期任务已创建并执行首次运行")


@router.post("/tasks/{task_id}/confirm")
def confirm_task(task_id: int, req: AgentConfirmReq, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = agent_service.confirm_task(db, user, task_id, req.confirm)
    return ok(data=_task_resp(task), message="已确认" if req.confirm else "已取消")


@router.get("/tasks")
def list_tasks(
    page: int | None = Query(None, ge=1, description="不传则保持旧行为：一次返回全部任务"),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """智能体任务列表。

    P1-8：原实现一次拉取用户全部任务（无上限）；传 page 时返回
    {total, page, page_size, items}，不传 page 时保持旧返回（纯数组），前端无需改动。
    """
    tasks, total = agent_service.list_tasks(db, user, page=page, page_size=page_size)
    data = [_task_resp(t) for t in tasks]
    if page is None:
        return ok(data=data)
    return ok(data={"total": total, "page": page, "page_size": page_size, "items": data})


@router.get("/tasks/{task_id}")
def get_task(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = agent_service.get_task(db, user, task_id)
    return ok(data=_task_resp(task))


def _template_resp(tpl) -> dict:
    return AgentTemplateResp(
        id=tpl.id,
        template_name=tpl.template_name,
        task_type=tpl.task_type,
        selected_doc_ids=tpl.selected_doc_ids,
        params=tpl.params,
        schedule_type=tpl.schedule_type,
        schedule_cron=tpl.schedule_cron,
        notify_on_finish=tpl.notify_on_finish,
        canvas_json=tpl.canvas_json,
        create_time=tpl.create_time,
        update_time=tpl.update_time,
    ).model_dump(mode="json")


@router.post("/templates")
def create_template(req: AgentTemplateReq, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tpl = agent_service.create_template(db, user, req.model_dump())
    return ok(data=_template_resp(tpl), message="模板已保存")


@router.get("/templates")
def list_templates(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(data=[_template_resp(t) for t in agent_service.list_templates(db, user)])


@router.delete("/templates/{template_id}")
def delete_template(template_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    agent_service.delete_template(db, user, template_id)
    return ok(message="模板已删除")


@router.put("/templates/{template_id}")
def update_template(template_id: int, req: AgentTemplateReq, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tpl = agent_service.update_template(db, user, template_id, req.model_dump())
    return ok(data=_template_resp(tpl), message="模板已更新")


@router.post("/templates/{template_id}/run")
def run_template(template_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = agent_service.template_to_task(db, user, template_id)
    # 模板运行即执行：跳过人工确认，直接按模板配置（含画布引擎）运行。
    # 周期模板（daily/weekly）在创建阶段已同步执行并置为 finished，无需也不能再次确认。
    if task.status == "waiting_confirm":
        task = agent_service.confirm_task(db, user, task.id, True)
    return ok(data=_task_resp(task), message="已按模板创建任务并执行")
