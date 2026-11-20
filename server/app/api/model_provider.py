# -*- coding: utf-8 -*-
"""模型供应商管理接口（管理员）。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.code import CONFLICT, NOT_FOUND
from app.core.deps import get_db, require_admin
from app.core.response import BizError, ok
from app.models import ModelProvider, User
from app.schemas.model_provider import ProviderCreateReq, ProviderUpdateReq

router = APIRouter(prefix="/api/admin/model-providers", tags=["模型供应商"])


def _mask(key: str) -> str:
    """api_key 掩码展示：前 6 + **** + 后 4。"""
    if not key:
        return ""
    if len(key) <= 8:
        return key[:2] + "***"
    return key[:6] + "****" + key[-4:]


def provider_out(p: ModelProvider) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "base_url": p.base_url,
        "model": p.model,
        "api_key_masked": _mask(p.api_key),
        "api_key_configured": bool(p.api_key),
        "is_default": p.is_default,
        "enabled": p.enabled,
        "create_time": p.create_time.strftime("%Y-%m-%d %H:%M:%S") if p.create_time else None,
        "update_time": p.update_time.strftime("%Y-%m-%d %H:%M:%S") if p.update_time else None,
    }


def _clear_default(db: Session, keep_id: int | None = None) -> None:
    q = db.query(ModelProvider).filter(ModelProvider.is_default.is_(True))
    if keep_id is not None:
        q = q.filter(ModelProvider.id != keep_id)
    for row in q.all():
        row.is_default = False
    db.flush()


@router.get("")
def list_providers(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    rows = db.query(ModelProvider).order_by(ModelProvider.id.asc()).all()
    return ok(data=[provider_out(p) for p in rows])


@router.post("")
def create_provider(req: ProviderCreateReq, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    if db.query(ModelProvider).filter(ModelProvider.name == req.name.strip()).first():
        raise BizError(CONFLICT, "供应商名称已存在")
    if req.is_default:
        _clear_default(db)
    p = ModelProvider(
        name=req.name.strip(),
        base_url=req.base_url.strip().rstrip("/"),
        model=req.model.strip(),
        api_key=req.api_key.strip(),
        is_default=req.is_default,
        enabled=req.enabled,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return ok(data=provider_out(p), message="供应商已创建")


@router.put("/{provider_id}")
def update_provider(provider_id: int, req: ProviderUpdateReq, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    p = db.get(ModelProvider, provider_id)
    if not p:
        raise BizError(NOT_FOUND, "供应商不存在")
    if req.name is not None and req.name.strip() and req.name.strip() != p.name:
        if db.query(ModelProvider).filter(ModelProvider.name == req.name.strip(), ModelProvider.id != provider_id).first():
            raise BizError(CONFLICT, "供应商名称已存在")
        p.name = req.name.strip()
    if req.base_url is not None and req.base_url.strip():
        p.base_url = req.base_url.strip().rstrip("/")
    if req.model is not None and req.model.strip():
        p.model = req.model.strip()
    if req.api_key is not None and req.api_key.strip():
        p.api_key = req.api_key.strip()
    if req.enabled is not None:
        p.enabled = req.enabled
    if req.is_default is not None:
        if req.is_default:
            _clear_default(db, keep_id=p.id)
        p.is_default = req.is_default
    db.commit()
    db.refresh(p)
    return ok(data=provider_out(p), message="供应商已更新")


@router.delete("/{provider_id}")
def delete_provider(provider_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    p = db.get(ModelProvider, provider_id)
    if not p:
        raise BizError(NOT_FOUND, "供应商不存在")
    was_default = bool(p.is_default)
    db.delete(p)
    db.flush()
    # 删除的是默认供应商时，回落到剩余条目，避免系统出现"无默认供应商"的悬空状态
    if was_default:
        nxt = (
            db.query(ModelProvider)
            .filter(ModelProvider.enabled.is_(True))
            .order_by(ModelProvider.id.asc())
            .first()
        )
        if nxt is None:
            nxt = db.query(ModelProvider).order_by(ModelProvider.id.asc()).first()
        if nxt is not None:
            nxt.is_default = True
    db.commit()
    return ok(message="供应商已删除")


@router.post("/{provider_id}/set-default")
def set_default(provider_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    p = db.get(ModelProvider, provider_id)
    if not p:
        raise BizError(NOT_FOUND, "供应商不存在")
    _clear_default(db, keep_id=p.id)
    p.is_default = True
    db.commit()
    db.refresh(p)
    return ok(data=provider_out(p), message="已设为默认供应商")


def seed_default_providers() -> None:
    """幂等预置模型供应商：首次启动且表为空时写入 DeepSeek 默认条目与千问示例条目。"""
    from datetime import datetime

    from app.core.config import settings
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        if db.query(ModelProvider).count() > 0:
            return
        now = datetime.now()
        deepseek = ModelProvider(
            name="DeepSeek 默认",
            base_url="https://api.deepseek.com/v1",
            model=settings.LLM_MODEL,
            api_key=settings.DEEPSEEK_API_KEY or "",
            is_default=True,
            enabled=True,
            create_time=now,
            update_time=now,
        )
        qwen = ModelProvider(
            name="千问Qwen",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model="qwen-plus",
            api_key="",
            is_default=False,
            enabled=True,
            create_time=now,
            update_time=now,
        )
        db.add_all([deepseek, qwen])
        db.commit()
    finally:
        db.close()
