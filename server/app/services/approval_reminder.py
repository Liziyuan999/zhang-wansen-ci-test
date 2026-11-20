# -*- coding: utf-8 -*-
"""审批超时催办：超过 APPROVAL_REMINDER_HOURS 未处理的审批，自动向通知中心推送催办。

由 main.py 后台定时循环（约每分钟）调用 run_approval_reminder()，函数幂等：
- 仅处理 status=pending 且 apply_time <= now - N 小时 的申请；
- 同一申请两次催办至少间隔 APPROVAL_REMINDER_INTERVAL_MINUTES 分钟（记录 reminder_sent_at 防刷屏）。
覆盖三类审批：下载审批 / 退出审批 / 考勤补卡审批。

P1-7（N+1 消除）：原实现逐个审批 db.get(Team)/db.get(User)，并在 _managers 里逐条
db.get(User)（同一成员还会被 get 两次），一轮扫描产生 3N 次查询。现改为先收集本轮
全部待催办审批，再对团队、申请人、团队管理者各做一次 IN 批量查询。
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import AttendanceFixApproval, DownloadApproval, Team, TeamExitApproval, TeamMember, User
from app.services.notification_service import notify_user

logger = logging.getLogger(__name__)

_APPROVAL_MODELS = [
    (DownloadApproval, "下载审批"),
    (TeamExitApproval, "退出审批"),
    (AttendanceFixApproval, "考勤补卡审批"),
]


def _managers_map(db: Session, team_ids) -> dict[int, list[User]]:
    """批量取多支团队的管理者（owner/admin + 团队所有者），每类数据只发一次查询。"""
    ids = {i for i in team_ids if i is not None}
    if not ids:
        return {}
    rows = (
        db.query(TeamMember.team_id, TeamMember.user_id)
        .filter(TeamMember.team_id.in_(ids), TeamMember.role.in_(["owner", "admin"]))
        .all()
    )
    teams = {t.id: t for t in db.query(Team).filter(Team.id.in_(ids)).all()}
    user_ids = {uid for _, uid in rows} | {t.owner_id for t in teams.values() if t.owner_id}
    user_map = (
        {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}
    )
    result: dict[int, list[User]] = {}
    for team_id, uid in rows:
        u = user_map.get(uid)
        if u and u not in result.setdefault(team_id, []):
            result[team_id].append(u)
    for team in teams.values():
        owner = user_map.get(team.owner_id) if team.owner_id else None
        if owner:
            bucket = result.setdefault(team.id, [])
            if owner not in bucket:
                bucket.insert(0, owner)
    return result


def _managers(db: Session, team_id: int) -> list[User]:
    """单团队管理者查询（保留原函数签名，内部复用批量实现）。"""
    return _managers_map(db, [team_id]).get(team_id, [])


def run_approval_reminder() -> int:
    """扫描并推送超时催办；返回本次催办条数。"""
    reminded = 0
    cutoff = datetime.now() - timedelta(hours=settings.APPROVAL_REMINDER_HOURS)
    min_interval = timedelta(minutes=settings.APPROVAL_REMINDER_INTERVAL_MINUTES)

    db: Session = SessionLocal()
    try:
        # 第一步：一次性收齐本轮全部超时审批（三类审批各一次查询）
        pending: list[tuple[str, object]] = []
        for model, label in _APPROVAL_MODELS:
            overdue = (
                db.query(model)
                .filter(
                    model.status == "pending",
                    model.apply_time <= cutoff,
                    (model.reminder_sent_at.is_(None)) | (model.reminder_sent_at <= datetime.now() - min_interval),
                )
                .limit(50)
                .all()
            )
            pending.extend((label, ap) for ap in overdue)
        if not pending:
            return 0
        # 第二步：团队 / 申请人 / 管理者全部批量预加载，循环内不再查库
        team_ids = {ap.team_id for _, ap in pending if ap.team_id is not None}
        applicant_ids = {ap.applicant_id for _, ap in pending if ap.applicant_id is not None}
        teams_map = {t.id: t for t in db.query(Team).filter(Team.id.in_(team_ids)).all()} if team_ids else {}
        applicant_map = (
            {u.id: u for u in db.query(User).filter(User.id.in_(applicant_ids)).all()} if applicant_ids else {}
        )
        managers_map = _managers_map(db, team_ids)

        # 第三步：批量推送（notify_user 内部均为新增对象，最后由一次 commit 落库）
        for label, ap in pending:
            if ap.team_id not in teams_map:
                continue
            applicant = applicant_map.get(ap.applicant_id)
            hours = int((datetime.now() - ap.apply_time).total_seconds() // 3600)
            for mgr in managers_map.get(ap.team_id, []):
                if applicant and applicant.id == mgr.id:
                    continue
                notify_user(
                    db,
                    mgr.id,
                    "审批超时催办",
                    f"「{label}」申请（申请人：{applicant.username if applicant else ap.applicant_id}）已超过 {hours} 小时未处理，请尽快审批",
                    category="approval",
                    ntype="approval_reminder",
                    related_id=ap.team_id,
                )
            ap.reminder_sent_at = datetime.now()
            reminded += 1
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("审批超时催办执行失败")
    finally:
        db.close()
    if reminded:
        logger.info("审批超时催办：共推送 %d 条", reminded)
    return reminded
