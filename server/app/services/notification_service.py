# -*- coding: utf-8 -*-
"""通知写入服务：统一向个人通知中心(UserNotification)写团队动态/审批消息/系统消息。"""
from sqlalchemy.orm import Session

from app.models import TeamMember, UserNotification

CATEGORY_TEAM = "team"  # 团队动态
CATEGORY_APPROVAL = "approval"  # 审批消息
CATEGORY_SYSTEM = "system"  # 系统消息


def notify_user(
    db: Session,
    user_id: int,
    title: str,
    content: str,
    category: str = CATEGORY_SYSTEM,
    ntype: str = "system",
    related_id: int | None = None,
) -> UserNotification:
    """写入一条个人通知（不 commit，由调用方统一提交）。"""
    n = UserNotification(
        user_id=user_id,
        title=title[:128],
        content=content[:1000],
        category=category,
        ntype=ntype,
        related_id=related_id,
    )
    db.add(n)
    return n


def notify_team_members(
    db: Session,
    team_id: int,
    title: str,
    content: str,
    category: str = CATEGORY_TEAM,
    ntype: str = "team",
    exclude_user_id: int | None = None,
    related_id: int | None = None,
) -> int:
    """给团队成员批量写个人通知，返回写入条数（不 commit，由调用方统一提交）。"""
    members = db.query(TeamMember).filter(TeamMember.team_id == team_id).all()
    count = 0
    for m in members:
        if exclude_user_id is not None and m.user_id == exclude_user_id:
            continue
        notify_user(
            db,
            m.user_id,
            title,
            content,
            category=category,
            ntype=ntype,
            related_id=related_id,
        )
        count += 1
    return count
