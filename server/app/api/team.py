# -*- coding: utf-8 -*-
"""团队空间接口：创建 / 我的团队 / 详情 / 编辑 / 邀请 / 接受 / 撤销 / 移除成员 / 移交所有者。"""
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.code import CONFLICT, NO_PERMISSION, NOT_FOUND, PARAM_ERROR
from app.core.deps import get_current_user, get_db
from app.core.response import BizError, ok
from app.models import (
    AttendanceFixApproval,
    AttendanceRecord,
    DownloadApproval,
    Team,
    TeamExitApproval,
    TeamGeoConfig,
    TeamInvitation,
    TeamLog,
    TeamMember,
    TeamNotice,
    TeamNoticeRead,
    TeamRole,
    User,
)
from app.schemas.team import (
    CreateTeamReq,
    DepartmentNodeResp,
    InvitationResp,
    InviteInfoResp,
    InviteReq,
    JoinTeamReq,
    MemberResp,
    SetParentReq,
    TeamDetailResp,
    TeamLogResp,
    TeamResp,
    TransferReq,
    UpdateMemberPermsReq,
    UpdateMemberRoleReq,
    UpdateTeamReq,
)
from app.services.email import send_invitation_email

router = APIRouter(prefix="/api/team", tags=["团队空间"])

ACCEPT_BASE_URL = "http://localhost:5173/team/accept"
INVITE_EXPIRE_HOURS = 48


def _fmt(dt: datetime | None) -> str | None:
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else None


def _member_of(db: Session, team_id: int, user_id: int) -> TeamMember | None:
    return db.query(TeamMember).filter(TeamMember.team_id == team_id, TeamMember.user_id == user_id).first()


def _add_log(db: Session, team_id: int, user_id: int, action: str, message: str) -> None:
    """写入团队操作日志（留痕：加入/退出/邀请/角色变更/移交/解散等）。"""
    db.add(TeamLog(team_id=team_id, user_id=user_id, action=action, message=message[:255]))


def _team_user_map(db: Session, user_ids) -> dict[int, User]:
    """P1-7：按 id 集合一次性 IN 查询用户，替代循环 db.get(User, id) 的 N+1。"""
    ids = {i for i in user_ids if i is not None}
    if not ids:
        return {}
    return {u.id: u for u in db.query(User).filter(User.id.in_(ids)).all()}


def _member_resp(db: Session, tm: TeamMember, user_map: dict[int, User] | None = None) -> MemberResp:
    # P1-7：传入 user_map 时走批量预加载，避免按成员逐条 db.get 造成 N+1
    u = user_map.get(tm.user_id) if user_map is not None else db.get(User, tm.user_id)
    return MemberResp(
        user_id=tm.user_id,
        username=u.username if u else str(tm.user_id),
        email=u.email if u else "",
        role=tm.role,
        joined_at=_fmt(tm.joined_at),
        perms=tm.perms or [],
    )


def _invitation_resp(db: Session, inv: TeamInvitation, user_map: dict[int, User] | None = None) -> InvitationResp:
    # P1-7：批量预加载邀请人，避免逐条 db.get
    inviter = user_map.get(inv.inviter_id) if user_map is not None else db.get(User, inv.inviter_id)
    accept_url = f"{ACCEPT_BASE_URL}?token={inv.token}&email={inv.email}"
    return InvitationResp(
        id=inv.id,
        email=inv.email,
        status=inv.status,
        token=inv.token,
        accept_url=accept_url,
        inviter_name=inviter.username if inviter else None,
        expires_at=_fmt(inv.expires_at),
        create_time=_fmt(inv.create_time),
    )


_UNSET = object()


def _team_resp(
    db: Session,
    team: Team,
    user: User,
    owner_name=_UNSET,
    member_count=_UNSET,
    my_role=_UNSET,
) -> TeamResp:
    # P1-7：批量场景可预先算好负责人名/成员数/我的角色传入，避免每个团队 3 次查库
    if owner_name is _UNSET:
        owner = db.get(User, team.owner_id)
        owner_name = owner.username if owner else None
    if member_count is _UNSET:
        member_count = db.query(TeamMember).filter(TeamMember.team_id == team.id).count()
    if my_role is _UNSET:
        me = _member_of(db, team.id, user.id)
        my_role = me.role if me else "member"
    return TeamResp(
        id=team.id,
        name=team.name,
        description=team.description,
        owner_id=team.owner_id,
        owner_name=owner_name,
        member_count=member_count,
        my_role=my_role,
        create_time=_fmt(team.create_time),
    )


@router.post("/create")
def create_team(req: CreateTeamReq, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    name = req.name.strip()
    if not name:
        raise BizError(PARAM_ERROR, "团队名称不能为空")
    team = Team(name=name, description=req.description.strip() or None, owner_id=user.id)
    db.add(team)
    db.flush()
    db.add(TeamMember(team_id=team.id, user_id=user.id, role="owner"))
    db.commit()
    return ok(data=_team_resp(db, team, user), message="团队创建成功")


@router.get("/my")
def list_my_teams(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """我的团队列表：P1-7 批量取团队/负责人/成员数，消除逐团队 3 次查库。

    说明：该接口按 user_id 过滤（非全表加载），且前端（web/src/api/team.ts listMyTeams）
    直接消费数组，故保持原数组返回结构不变，仅做 N+1 优化。
    """
    rows = (
        db.query(TeamMember)
        .filter(TeamMember.user_id == user.id)
        .order_by(TeamMember.id.desc())
        .all()
    )
    team_ids = [m.team_id for m in rows]
    if not team_ids:
        return ok(data=[])
    teams_map = {t.id: t for t in db.query(Team).filter(Team.id.in_(team_ids)).all()}
    owner_ids = {t.owner_id for t in teams_map.values() if t.owner_id is not None}
    owner_map = (
        {uid: uname for uid, uname in db.query(User.id, User.username).filter(User.id.in_(owner_ids)).all()}
        if owner_ids
        else {}
    )
    count_map = dict(
        db.query(TeamMember.team_id, func.count(TeamMember.id))
        .filter(TeamMember.team_id.in_(team_ids))
        .group_by(TeamMember.team_id)
        .all()
    )
    my_role_map = {m.team_id: m.role for m in rows}
    teams = []
    for m in rows:
        team = teams_map.get(m.team_id)
        if not team:
            continue
        teams.append(
            _team_resp(
                db,
                team,
                user,
                owner_name=owner_map.get(team.owner_id),
                member_count=count_map.get(team.id, 0),
                my_role=my_role_map.get(team.id, "member"),
            )
        )
    return ok(data=teams)


@router.get("/invite/info")
def invite_info(token: str = Query(...), db: Session = Depends(get_db)):
    inv = db.query(TeamInvitation).filter(TeamInvitation.token == token).first()
    if not inv:
        raise BizError(NOT_FOUND, "邀请链接无效或不存在")
    team = db.get(Team, inv.team_id)
    inviter = db.get(User, inv.inviter_id)
    if not team or not inviter:
        raise BizError(NOT_FOUND, "邀请信息不完整，请重新发起邀请")
    status = inv.status
    if status == "pending" and inv.expires_at < datetime.now():
        status = "expired"
    return ok(
        data=InviteInfoResp(
            team_id=team.id,
            team_name=team.name,
            inviter_id=inviter.id,
            inviter_name=inviter.username,
            inviter_email=inviter.email,
            email=inv.email,
            status=status,
            expires_at=_fmt(inv.expires_at),
        )
    )


@router.post("/invite/{token}/accept")
def accept_invite(token: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    inv = db.query(TeamInvitation).filter(TeamInvitation.token == token).first()
    if not inv:
        raise BizError(NOT_FOUND, "邀请链接无效或不存在")
    if inv.status != "pending":
        raise BizError(CONFLICT, "该邀请已处理，无法再次接受")
    if inv.expires_at < datetime.now():
        inv.status = "expired"
        db.commit()
        raise BizError(CONFLICT, "邀请已过期，请联系邀请人重新邀请")
    if user.email.lower() != inv.email.lower():
        raise BizError(NO_PERMISSION, f"该邀请仅限 {inv.email} 接受，当前账号邮箱不匹配")
    team = db.get(Team, inv.team_id)
    if not team:
        raise BizError(NOT_FOUND, "团队不存在")
    existing = _member_of(db, team.id, user.id)
    if not existing:
        db.add(TeamMember(team_id=team.id, user_id=user.id, role="member"))
    inv.status = "accepted"
    db.commit()
    return ok(data={"team_id": team.id, "team_name": team.name}, message="已加入团队")


@router.post("/invite/{invitation_id}/revoke")
def revoke_invite(invitation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    inv = db.get(TeamInvitation, invitation_id)
    if not inv:
        raise BizError(NOT_FOUND, "邀请记录不存在")
    me = _member_of(db, inv.team_id, user.id)
    if not me or me.role not in ("owner", "admin"):
        raise BizError(NO_PERMISSION, "仅团队所有者或管理员可撤销邀请")
    if inv.status != "pending":
        raise BizError(CONFLICT, "仅可撤销待接受的邀请")
    inv.status = "declined"
    _add_log(db, inv.team_id, user.id, "invite_revoke", f"{user.username} 撤销了发往 {inv.email} 的邀请")
    db.commit()
    return ok(message="邀请已撤销")


@router.get("/departments")
def department_tree(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """组织架构树：当前用户可管理的部门（含其子孙团队），未设置 parent_id 的团队为顶级部门。

    P1-7 / P1-8：原实现 `db.query(Team).all()` 全表加载后在内存里做子孙遍历，且每个节点
    各自 count 成员 + 查我的角色（N+1）。改为：按 parent_id 逐层向下取子孙（只取命中行），
    进而只加载可见团队，成员数与我的角色各用一次批量查询。
    """
    my_rows = db.query(TeamMember).filter(TeamMember.user_id == user.id).all()
    my_teams = [m.team_id for m in my_rows]
    if not my_teams:
        return ok(data=[])
    role_map = {m.team_id: m.role for m in my_rows}
    managed_ids = [tid for tid, r in role_map.items() if r in ("owner", "admin")]
    # 逐层向下收集管理部门的子孙团队（不再全表加载 Team）
    visible_ids = set(my_teams)
    frontier = list(managed_ids)
    while frontier:
        rows = db.query(Team.id).filter(Team.parent_id.in_(frontier)).all()
        nxt = [r[0] for r in rows if r[0] not in visible_ids]
        if not nxt:
            break
        visible_ids.update(nxt)
        frontier = nxt
    all_teams = {
        t.id: t for t in db.query(Team).filter(Team.id.in_(visible_ids)).all()
    } if visible_ids else {}
    count_map = dict(
        db.query(TeamMember.team_id, func.count(TeamMember.id))
        .filter(TeamMember.team_id.in_(visible_ids))
        .group_by(TeamMember.team_id)
        .all()
    ) if visible_ids else {}
    child_map: dict[int, list[Team]] = {}
    for t in all_teams.values():
        if t.id in visible_ids and t.parent_id in visible_ids:
            child_map.setdefault(t.parent_id, []).append(t)
    roots = [t for t in all_teams.values() if t.id in visible_ids and (t.parent_id is None or t.parent_id not in visible_ids)]
    roots.sort(key=lambda t: t.id)
    data = [_department_node(t, child_map, count_map, role_map) for t in roots]
    return ok(data=data)


@router.get("/{team_id}")
def get_team(team_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    team = db.get(Team, team_id)
    if not team:
        raise BizError(NOT_FOUND, "团队不存在")
    me = _member_of(db, team.id, user.id)
    if not me:
        raise BizError(NO_PERMISSION, "您不是该团队成员")
    members = db.query(TeamMember).filter(TeamMember.team_id == team.id).order_by(TeamMember.id.asc()).all()
    invitations = (
        db.query(TeamInvitation)
        .filter(TeamInvitation.team_id == team.id)
        .order_by(TeamInvitation.id.desc())
        .all()
    )
    # P1-7：成员、邀请人各用一次 IN 批量取用户，替代循环 db.get
    member_user_map = _team_user_map(db, [m.user_id for m in members])
    inviter_user_map = _team_user_map(db, [i.inviter_id for i in invitations])
    detail = TeamDetailResp(
        **_team_resp(db, team, user, member_count=len(members), my_role=me.role).model_dump(),
        members=[_member_resp(db, m, member_user_map) for m in members],
        invitations=[_invitation_resp(db, inv, inviter_user_map) for inv in invitations],
    )
    return ok(data=detail)


@router.put("/{team_id}")
def update_team(
    team_id: int, req: UpdateTeamReq, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    team = db.get(Team, team_id)
    if not team:
        raise BizError(NOT_FOUND, "团队不存在")
    me = _member_of(db, team.id, user.id)
    if not me or me.role not in ("owner", "admin"):
        raise BizError(NO_PERMISSION, "仅团队所有者或管理员可编辑团队")
    name = req.name.strip()
    if not name:
        raise BizError(PARAM_ERROR, "团队名称不能为空")
    team.name = name
    team.description = req.description.strip() or None
    db.commit()
    return ok(data=_team_resp(db, team, user), message="团队信息已更新")


@router.post("/{team_id}/invite")
def invite_member(
    team_id: int, req: InviteReq, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    team = db.get(Team, team_id)
    if not team:
        raise BizError(NOT_FOUND, "团队不存在")
    me = _member_of(db, team.id, user.id)
    if not me or me.role not in ("owner", "admin"):
        raise BizError(NO_PERMISSION, "仅团队所有者或管理员可邀请成员")

    email = req.qq_email.strip().lower()
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user and _member_of(db, team.id, existing_user.id):
        raise BizError(CONFLICT, "该用户已在团队中，无需重复邀请")
    dup = (
        db.query(TeamInvitation)
        .filter(TeamInvitation.team_id == team.id, TeamInvitation.email == email, TeamInvitation.status == "pending")
        .first()
    )
    if dup:
        raise BizError(CONFLICT, "该邮箱已有待接受的邀请，请勿重复邀请")

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(hours=INVITE_EXPIRE_HOURS)
    inv = TeamInvitation(
        team_id=team.id,
        inviter_id=user.id,
        email=email,
        token=token,
        status="pending",
        expires_at=expires_at,
    )
    db.add(inv)
    _add_log(db, team.id, user.id, "invite", f"邀请 {email} 加入团队")
    db.commit()

    accept_url = f"{ACCEPT_BASE_URL}?token={token}&email={email}"
    send_invitation_email(email, team.name, user.username, accept_url)
    return ok(data=_invitation_resp(db, inv), message="邀请已发送至邮箱")


@router.delete("/{team_id}/member/{user_id}")
def remove_member(
    team_id: int, user_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    team = db.get(Team, team_id)
    if not team:
        raise BizError(NOT_FOUND, "团队不存在")
    me = _member_of(db, team.id, user.id)
    if not me or me.role not in ("owner", "admin"):
        raise BizError(NO_PERMISSION, "仅团队所有者或管理员可移除成员")
    target = db.get(User, user_id)
    if not target:
        raise BizError(NOT_FOUND, "成员不存在")
    tm = _member_of(db, team.id, user_id)
    if not tm:
        raise BizError(NOT_FOUND, "该成员不在团队中")
    if tm.role == "owner":
        raise BizError(CONFLICT, "团队所有者不可被移除")
    if me.role == "admin" and tm.role != "member":
        raise BizError(NO_PERMISSION, "管理员仅可移除普通成员")
    if user_id == user.id:
        raise BizError(CONFLICT, "不能移除自己，如需退出团队请联系所有者处理")
    db.delete(tm)
    _add_log(db, team.id, user.id, "member_remove", f"{user.username} 移除了成员 {target.username}")
    db.commit()
    return ok(message=f"成员 {target.username} 已移除")


@router.put("/{team_id}/member/{user_id}/role")
def update_member_role(
    team_id: int, user_id: int, req: UpdateMemberRoleReq, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """调整成员角色（member/admin/owner）。owner 可调整任意非 owner 成员；admin 仅可调整普通成员；owner 角色不可被修改。"""
    team = db.get(Team, team_id)
    if not team:
        raise BizError(NOT_FOUND, "团队不存在")
    me = _member_of(db, team.id, user.id)
    if not me:
        raise BizError(NO_PERMISSION, "您不是该团队成员")
    tm = _member_of(db, team.id, user_id)
    if not tm:
        raise BizError(NOT_FOUND, "该成员不在团队中")
    role = req.role
    if tm.role == "owner":
        raise BizError(CONFLICT, "团队所有者角色不可被修改")
    if role.startswith("custom_"):
        # 自定义角色必须属于本团队
        custom = db.query(TeamRole).filter(TeamRole.role_key == role, TeamRole.team_id == team.id).first()
        if not custom:
            raise BizError(PARAM_ERROR, "自定义角色不存在或不属于当前团队")
    if me.role == "owner":
        if user_id == user.id:
            raise BizError(CONFLICT, "不能修改自己的角色，如需移交所有权请使用移交功能")
        if role == "owner":
            # 设为所有者 = 触发移交语义：原所有者降为普通成员，团队 owner_id 同步更新
            me.role = "member"
            tm.role = "owner"
            team.owner_id = user_id
            _add_log(db, team.id, user.id, "owner_transfer", f"{user.username} 将团队所有者移交给了 {tm.user_id}")
            db.commit()
            return ok(message=f"已将 {tm.user_id} 设为团队所有者")
        tm.role = role
        _add_log(db, team.id, user.id, "role_change", f"{user.username} 将成员 {tm.user_id} 角色调整为 {role}")
        db.commit()
        return ok(message="成员角色已更新")
    if me.role == "admin":
        if tm.role != "member":
            raise BizError(NO_PERMISSION, "管理员仅可调整普通成员角色")
        if role == "owner":
            raise BizError(NO_PERMISSION, "仅团队所有者可指定所有者角色")
        tm.role = role
        _add_log(db, team.id, user.id, "role_change", f"{user.username} 将成员 {tm.user_id} 角色调整为 {role}")
        db.commit()
        return ok(message="成员角色已更新")
    raise BizError(NO_PERMISSION, "仅团队所有者或管理员可调整成员角色")


@router.post("/{team_id}/transfer")
def transfer_owner(
    team_id: int, req: TransferReq, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    team = db.get(Team, team_id)
    if not team:
        raise BizError(NOT_FOUND, "团队不存在")
    me = _member_of(db, team.id, user.id)
    if not me or me.role != "owner":
        raise BizError(NO_PERMISSION, "仅团队所有者可移交所有权")
    if req.target_user_id == user.id:
        raise BizError(PARAM_ERROR, "不能移交给当前所有者本人")
    tm = _member_of(db, team.id, req.target_user_id)
    if not tm:
        raise BizError(NOT_FOUND, "目标用户不在团队中")
    tm.role = "owner"
    me.role = "member"
    team.owner_id = req.target_user_id
    _add_log(db, team.id, user.id, "owner_transfer", f"{user.username} 将团队所有权移交给 {tm.user_id}")
    db.commit()
    return ok(message="团队所有权已移交")


def _extract_token(raw: str) -> str:
    """从用户输入中提取邀请 token：兼容直接粘贴 token 或完整邀请链接（含 token= 查询参数）。"""
    value = raw.strip()
    if "token=" in value:
        value = value.split("token=", 1)[1]
        value = value.split("&", 1)[0]
    return value.strip()


@router.post("/join")
def join_team(req: JoinTeamReq, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """通过邀请链接/token 加入团队：校验 token 有效、未过期、当前邮箱与邀请邮箱一致。"""
    token = _extract_token(req.token)
    if not token:
        raise BizError(PARAM_ERROR, "请提供有效的邀请链接或 token")
    inv = db.query(TeamInvitation).filter(TeamInvitation.token == token).first()
    if not inv:
        raise BizError(NOT_FOUND, "邀请链接无效或不存在")
    if inv.status != "pending":
        raise BizError(CONFLICT, "该邀请已使用或已撤销，无法再次加入")
    if inv.expires_at < datetime.now():
        inv.status = "expired"
        db.commit()
        raise BizError(CONFLICT, "邀请已过期，请联系邀请人重新邀请")
    if user.email.lower() != inv.email.lower():
        raise BizError(NO_PERMISSION, f"该邀请仅限 {inv.email} 接受，当前账号邮箱不匹配，无法加入")
    team = db.get(Team, inv.team_id)
    if not team:
        raise BizError(NOT_FOUND, "团队不存在")
    existing = _member_of(db, team.id, user.id)
    if existing:
        raise BizError(CONFLICT, "您已在该团队中，无需重复加入")
    db.add(TeamMember(team_id=team.id, user_id=user.id, role="member"))
    inv.status = "accepted"
    _add_log(db, team.id, user.id, "join", f"{user.username} 通过邀请链接加入团队")
    db.commit()
    return ok(data=_team_resp(db, team, user), message="已成功加入团队")


@router.post("/{team_id}/leave")
def leave_team(team_id: int, reason: str = Query(""), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """成员退出团队：提交退出申请，由 owner/admin 审批通过后自动移除成员。"""
    from app.models import TeamExitApproval, UserNotification
    from app.services.audit import record_audit

    team = db.get(Team, team_id)
    if not team:
        raise BizError(NOT_FOUND, "团队不存在")
    me = _member_of(db, team.id, user.id)
    if not me:
        raise BizError(NO_PERMISSION, "您不是该团队成员")
    if me.role == "owner":
        raise BizError(CONFLICT, "团队所有者不能退出，请先移交所有权或解散团队")
    dup = (
        db.query(TeamExitApproval)
        .filter(TeamExitApproval.team_id == team.id, TeamExitApproval.applicant_id == user.id, TeamExitApproval.status == "pending")
        .first()
    )
    if dup:
        raise BizError(CONFLICT, "您已提交过退出申请，请等待审批")
    ap = TeamExitApproval(team_id=team.id, applicant_id=user.id, reason=(reason or "")[:255], status="pending")
    db.add(ap)
    db.commit()

    managers = db.query(TeamMember).filter(TeamMember.team_id == team.id, TeamMember.role.in_(["owner", "admin"])).all()
    for m in managers:
        if m.user_id == user.id:
            continue
        db.add(
            UserNotification(
                user_id=m.user_id,
                title="新的退出审批申请",
                content=f"{user.username} 申请退出团队「{team.name}」，等待您审批",
                category="approval",
                ntype="approval",
                related_id=team.id,
            )
        )
    db.commit()
    record_audit(db, user, "exit_apply", "team", f"提交退出团队「{team.name}」申请")
    return ok(message="退出申请已提交，等待团队所有者审批")


@router.delete("/{team_id}")
def dissolve_team(team_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """解散团队（仅 owner）：清理成员、邀请、通知、日志后删除团队。"""
    team = db.get(Team, team_id)
    if not team:
        raise BizError(NOT_FOUND, "团队不存在")
    me = _member_of(db, team.id, user.id)
    if not me or me.role != "owner":
        raise BizError(NO_PERMISSION, "仅团队所有者可解散团队")
    db.query(TeamMember).filter(TeamMember.team_id == team.id).delete()
    db.query(TeamInvitation).filter(TeamInvitation.team_id == team.id).delete()
    notice_ids = [n.id for n in db.query(TeamNotice.id).filter(TeamNotice.team_id == team.id).all()]
    if notice_ids:
        db.query(TeamNoticeRead).filter(TeamNoticeRead.notice_id.in_(notice_ids)).delete()
    db.query(TeamNotice).filter(TeamNotice.team_id == team.id).delete()
    db.query(TeamLog).filter(TeamLog.team_id == team.id).delete()
    # 关联业务数据一并清理，避免遗留孤儿记录（team 主键在 SQLite 下可能被复用，残留会导致新团队“继承”旧数据）
    db.query(DownloadApproval).filter(DownloadApproval.team_id == team.id).delete()
    db.query(TeamExitApproval).filter(TeamExitApproval.team_id == team.id).delete()
    db.query(AttendanceFixApproval).filter(AttendanceFixApproval.team_id == team.id).delete()
    db.query(AttendanceRecord).filter(AttendanceRecord.team_id == team.id).delete()
    db.query(TeamGeoConfig).filter(TeamGeoConfig.team_id == team.id).delete()
    db.query(TeamRole).filter(TeamRole.team_id == team.id).delete()
    db.delete(team)
    db.commit()
    return ok(message="团队已解散")


@router.get("/{team_id}/logs")
def team_logs(
    team_id: int,
    page: int | None = Query(None, ge=1, description="不传则保持旧行为：返回最近 50 条"),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """团队动态/操作日志：仅团队成员可见，按时间倒序。

    P1-8：原实现固定 limit 50 且无总数，现支持分页（默认 50、上限 200）并返回真实 total；
    不传 page 时保持旧返回结构（最近 50 条数组），前端无需改动。
    """
    team = db.get(Team, team_id)
    if not team:
        raise BizError(NOT_FOUND, "团队不存在")
    me = _member_of(db, team.id, user.id)
    if not me:
        raise BizError(NO_PERMISSION, "您不是该团队成员")
    # 修复 P2-1：团队操作日志包含成员变更、审批、配置等敏感信息，此前仅校验"是成员"即可读全量，
    # 普通成员可越权查看管理动作。现要求：owner/admin 天然可看；其他成员需被显式授予 view_audit 权限位。
    if me.role not in ("owner", "admin") and "view_audit" not in (me.perms or []):
        raise BizError(NO_PERMISSION, "无查看权限：需要「查看审计日志」权限，请联系团队管理员开通")
    q = db.query(TeamLog).filter(TeamLog.team_id == team.id)
    if page is None:
        logs = q.order_by(TeamLog.id.desc()).limit(50).all()
        total = len(logs)
    else:
        total = q.count()
        logs = q.order_by(TeamLog.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    # P1-7：日志原本逐条 db.get(User)，改为一次 IN 批量取
    log_user_map = _team_user_map(db, [log.user_id for log in logs])
    data = []
    for log in logs:
        u = log_user_map.get(log.user_id)
        data.append(
            TeamLogResp(
                id=log.id,
                user_id=log.user_id,
                username=u.username if u else str(log.user_id),
                action=log.action,
                message=log.message,
                create_time=_fmt(log.create_time),
            ).model_dump(mode="json")
        )
    if page is None:
        return ok(data=data)
    return ok(data={"total": total, "page": page, "page_size": page_size, "items": data})


# ---------- M6 组织架构：部门树 / 细粒度权限 ----------

PERM_ALL = ["manage_docs", "manage_members", "send_notice", "view_audit", "manage_departments"]


def _department_node(
    team: Team,
    child_map: dict[int, list[Team]],
    count_map: dict[int, int] | None = None,
    role_map: dict[int, str] | None = None,
) -> DepartmentNodeResp:
    # P1-7：成员数与我的角色由调用方批量预加载，避免每个节点各查一次库
    member_count = (count_map or {}).get(team.id, 0)
    my_role = (role_map or {}).get(team.id, "member")
    children = [
        _department_node(c, child_map, count_map, role_map) for c in child_map.get(team.id, [])
    ]
    return DepartmentNodeResp(
        team_id=team.id,
        name=team.name,
        description=team.description,
        parent_id=team.parent_id,
        member_count=member_count,
        my_role=my_role,
        children=children,
    )


@router.put("/{team_id}/parent")
def set_team_parent(
    team_id: int, req: SetParentReq, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """设置团队上级部门：仅 owner/admin 可操作；禁止把上级设为自己的子孙（防环）。"""
    team = db.get(Team, team_id)
    if not team:
        raise BizError(NOT_FOUND, "团队不存在")
    me = _member_of(db, team.id, user.id)
    if not me or me.role not in ("owner", "admin"):
        raise BizError(NO_PERMISSION, "仅团队所有者或管理员可设置上级部门")
    parent_id = req.parent_id
    if parent_id == team.id:
        raise BizError(PARAM_ERROR, "不能将自身设为上级部门")
    if parent_id is not None:
        parent = db.get(Team, parent_id)
        if not parent:
            raise BizError(NOT_FOUND, "上级部门不存在")
        # 防环：上级不能是自己的子孙
        cursor: int | None = parent_id
        seen = set()
        while cursor is not None:
            if cursor == team.id:
                raise BizError(PARAM_ERROR, "不能将子孙团队设为上级部门（会形成循环）")
            if cursor in seen:
                break
            seen.add(cursor)
            p = db.get(Team, cursor)
            cursor = p.parent_id if p else None
    team.parent_id = parent_id
    _add_log(db, team.id, user.id, "structure_change", f"{user.username} 设置了上级部门 {'无' if parent_id is None else parent_id}")
    db.commit()
    return ok(message="上级部门已更新")


@router.put("/{team_id}/member/{user_id}/perms")
def update_member_perms(
    team_id: int, user_id: int, req: UpdateMemberPermsReq, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """细粒度成员权限配置：owner/admin 可设置成员权限位（manage_docs/manage_members/send_notice/view_audit/manage_departments）。"""
    team = db.get(Team, team_id)
    if not team:
        raise BizError(NOT_FOUND, "团队不存在")
    me = _member_of(db, team.id, user.id)
    if not me or me.role not in ("owner", "admin"):
        raise BizError(NO_PERMISSION, "仅团队所有者或管理员可配置成员权限")
    tm = _member_of(db, team.id, user_id)
    if not tm:
        raise BizError(NOT_FOUND, "该成员不在团队中")
    if tm.role == "owner":
        raise BizError(CONFLICT, "团队所有者拥有全部权限，无需配置")
    invalid = [p for p in req.perms if p not in PERM_ALL]
    if invalid:
        raise BizError(PARAM_ERROR, f"不支持的权限位：{','.join(invalid)}")
    tm.perms = list(dict.fromkeys(req.perms))
    _add_log(db, team.id, user.id, "perm_change", f"{user.username} 更新了成员 {tm.user_id} 的权限配置")
    db.commit()
    return ok(data=_member_resp(db, tm), message="成员权限已更新")
