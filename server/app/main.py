# -*- coding: utf-8 -*-
"""FastAPI 应用入口。"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, agent, audit, auth, chat, dashboard, demo, document, document_copilot, kg, model_provider, notice, org_extra, report, team, user
from app.api.model_provider import seed_default_providers
from app.core.config import settings
from app.core.response import register_exception_handlers
from app.db.base import Base
from app.db.migrate import apply_column_patches
from app.db.indexes import ensure_indexes
from app.db.session import SessionLocal, engine
from app.models import Base as ModelBase  # noqa: F401  确保模型注册
from app.services.agent_service import run_scheduled_tasks
from app.services.approval_reminder import run_approval_reminder
from app.services.audit import audit_middleware
from app.services.cleanup import periodic_cleanup
from app.services import doc_service
from app.services.security_helper import get_user_from_token

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

_cleanup_task: asyncio.Task | None = None
_schedule_task: asyncio.Task | None = None


async def _scheduled_loop() -> None:
    """周期任务：Agent 任务扫描 + 审批超时催办，每 60 秒一次。"""
    while True:
        try:
            run_scheduled_tasks()
        except Exception:  # noqa: BLE001
            logger.exception("Agent 周期任务扫描异常")
        try:
            run_approval_reminder()
        except Exception:  # noqa: BLE001
            logger.exception("审批超时催办执行异常")
        await asyncio.sleep(60)


# ===== 逐行注释：应用生命周期（FastAPI lifespan 启动/关闭钩子） =====
# 1. create_all：启动时自动建表（幂等，表已存在则跳过），配合 models 下全部 Base 子类注册。
# 2. apply_column_patches：对存量表执行幂等补列迁移（新增字段不丢旧数据）。
# 3. seed_default_providers：首次启动预置模型供应商（DeepSeek 默认 + 千问示例），供对话/Agent 选用。
# 4. periodic_cleanup：创建后台任务，每天清理过期数据（验证码/临时文件等），无需 Redis/Celery。
# 5. _scheduled_loop：每分钟扫描 Agent 任务执行 + 审批超时催办。
# 6. yield 之后为关闭阶段：取消两个后台任务，保证进程优雅退出不残留协程。
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时自动建表（幂等）
    ModelBase.metadata.create_all(bind=engine)
    # 已有表补充新列（幂等迁移）
    apply_column_patches(engine)
    # P1-2：高频查询列索引补齐（CREATE INDEX IF NOT EXISTS，幂等，重复启动无副作用）
    ensure_indexes(engine)
    # 预置模型供应商（首次启动：DeepSeek 默认 + 千问示例）
    seed_default_providers()
    logger.info("数据库表已初始化: %s", settings.DATABASE_URL)
    # 断点恢复：解析为 BackgroundTask 内存执行，进程重启后 pending/processing 文档无人接管会永久卡死，
    # 启动时统一置为 failed 并给出可重试提示，用户点"重新解析"即可重新入队（人工可感知，不会无限等待）。
    _db = SessionLocal()
    try:
        _n = doc_service.recover_stuck_documents(_db)
        if _n:
            logger.warning("启动恢复：%d 个中断的文档解析任务已标记为失败（可重新解析）", _n)
    finally:
        _db.close()
    # P1-4：重放关系库/向量库双写补偿队列（上次进程内向量删除失败的 doc_id，此处继续清理）
    try:
        from app.api.document import vector_store as _vector_store

        _db2 = SessionLocal()
        try:
            _fixed = doc_service.reconcile_vector_orphans(_db2, _vector_store)
            if _fixed:
                logger.warning("启动补偿：已清理 %d 个已删文档的残留向量", _fixed)
        finally:
            _db2.close()
    except Exception as exc:  # pragma: no cover - 补偿失败不影响服务启动
        logger.warning("向量双写补偿重放失败（下次启动继续）: %s", exc)
    # 启动过期数据定时清理（每天一次，无需 Redis/Celery）
    global _cleanup_task
    _cleanup_task = asyncio.create_task(periodic_cleanup())
    # 启动 Agent 周期任务扫描（每分钟一次）
    global _schedule_task
    _schedule_task = asyncio.create_task(_scheduled_loop())
    yield
    if _cleanup_task:
        _cleanup_task.cancel()
    if _schedule_task:
        _schedule_task.cancel()


# ===== 逐行注释：应用组装（中间件 + 异常处理 + 路由挂载） =====
# 1. FastAPI 实例：title/version 来自 settings，lifespan 绑定上述启动/关闭钩子。
# 2. CORSMiddleware：允许前端开发端口（5173）跨域，携带凭证（Authorization 头）访问。
# 3. audit_middleware：HTTP 级审计中间件，自动记录业务操作审计日志（借助 get_user_from_token
#    从 Authorization 头解析当前用户，失败则记匿名操作）。
# 4. register_exception_handlers：统一异常转 JSON 响应（BizError -> code/message/data）。
# 5. api_router 汇总 16 个业务路由模块并逐个 include_router；新增模块需在此登记才会暴露。
# 6. /api/health 与 / 为探活接口：不参与鉴权，供负载均衡/健康检查使用。
app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(audit_middleware(SessionLocal, get_user_from_token))

register_exception_handlers(app)

api_router = [auth.router, user.router, document.router, document_copilot.router, chat.router, agent.router, admin.router, team.router, notice.router, audit.router, dashboard.router, report.router, model_provider.router, org_extra.router, kg.router, demo.router]
for r in api_router:
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"code": 0, "message": "ok", "data": {"app": settings.APP_NAME, "version": settings.APP_VERSION}}


@app.get("/")
def root():
    return {"code": 0, "message": "知寻 KnowSeek 后端服务运行中", "data": None}
