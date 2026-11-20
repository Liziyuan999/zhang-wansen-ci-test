# -*- coding: utf-8 -*-
"""过期数据定时清理：过期 refresh_token 与 email_code 记录。

不依赖 Celery/Redis，由 FastAPI 生命周期后台任务驱动，每天执行一次。
"""
import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import delete

from app.db.session import SessionLocal
from app.models import EmailCode, RefreshToken

logger = logging.getLogger(__name__)

_CLEANUP_INTERVAL_SECONDS = 24 * 3600
# 已使用验证码保留窗口：超过该天数的一并删除
_USED_CODE_KEEP_DAYS = 7


def cleanup_expired_records() -> dict[str, int]:
    """清理过期 token 与验证码，返回删除条数。"""
    now = datetime.now()
    with SessionLocal() as db:
        r1 = db.execute(delete(RefreshToken).where(RefreshToken.expires_at < now))
        r2 = db.execute(
            delete(EmailCode).where(
                (EmailCode.expires_at < now)
                | ((EmailCode.used.is_(True)) & (EmailCode.create_time < now - timedelta(days=_USED_CODE_KEEP_DAYS)))
            )
        )
        db.commit()
        return {"refresh_tokens": r1.rowcount or 0, "email_codes": r2.rowcount or 0}


async def periodic_cleanup() -> None:
    """后台循环：启动时先执行一次，之后每 24 小时执行一次。"""
    while True:
        try:
            result = cleanup_expired_records()
            logger.info("定时清理完成: %s", result)
        except Exception as exc:  # pragma: no cover
            logger.warning("定时清理失败: %s", exc)
        await asyncio.sleep(_CLEANUP_INTERVAL_SECONDS)
