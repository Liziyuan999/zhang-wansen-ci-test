# -*- coding: utf-8 -*-
"""用户与部门接口。"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.response import BizError, ok
from app.core.security import hash_password, verify_password
from app.core.totp import generate_secret, otpauth_url, verify_totp
from app.models import Department, SecurityEvent, User
from app.schemas.auth import (
    AvatarUploadReq,
    ChangePasswordReq,
    SecurityEventResp,
    TotpDisableReq,
    TotpEnableReq,
    TotpSetupResp,
    UpdateProfileReq,
    UserInfo,
    UserProfile,
)

router = APIRouter(prefix="/api", tags=["用户"])


def _client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    fwd = request.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else request.client.host if request.client else None


def _add_security_event(db: Session, user_id: int, event_type: str, description: str, ip: str | None = None) -> None:
    db.add(SecurityEvent(user_id=user_id, event_type=event_type, description=description, ip=ip))


def _security_event_resp(e: SecurityEvent) -> SecurityEventResp:
    return SecurityEventResp(id=e.id, event_type=e.event_type, description=e.description, ip=e.ip, create_time=e.create_time)


@router.get("/departments")
def list_departments(db: Session = Depends(get_db)):
    rows = db.query(Department).order_by(Department.id.asc()).all()
    return ok(data=[{"id": d.id, "dept_name": d.dept_name} for d in rows])


@router.get("/user/info")
def user_info(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    dept = db.get(Department, user.dept_id)
    info = UserInfo(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        status=user.status,
        dept_id=user.dept_id,
        dept_name=dept.dept_name if dept else None,
        avatar=user.avatar,
        totp_enabled=user.totp_enabled or False,
        last_login_time=user.last_login_time,
    )
    return ok(data=info)


def _profile_of(user: User, db: Session) -> UserProfile:
    dept = db.get(Department, user.dept_id)
    return UserProfile(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        status=user.status,
        dept_id=user.dept_id,
        dept_name=dept.dept_name if dept else None,
        avatar=user.avatar,
        totp_enabled=user.totp_enabled or False,
        has_password=bool(user.password_hash) and user.password_hash.startswith("$2"),
        last_login_time=user.last_login_time,
        create_time=user.create_time,
        update_time=user.update_time,
    )


@router.get("/user/profile")
def get_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """个人中心：完整资料。"""
    return ok(data=_profile_of(user, db))


@router.put("/user/profile")
def update_profile(
    req: UpdateProfileReq,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """个人中心：更新昵称 / 部门。"""
    if req.username is not None:
        if req.username != user.username:
            exists = db.query(User).filter(User.username == req.username, User.id != user.id).first()
            if exists:
                raise BizError(40001, "昵称已被占用")
            user.username = req.username.strip()
    if req.dept_id is not None:
        if not db.get(Department, req.dept_id):
            raise BizError(40002, "部门不存在")
        user.dept_id = req.dept_id
    db.add(user)
    db.commit()
    db.refresh(user)
    return ok(data=_profile_of(user, db), message="资料已更新")


@router.put("/user/password")
def change_password(
    req: ChangePasswordReq,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """个人中心：修改密码（校验旧密码）；无密码老用户兼容首次设置（无需原密码）。"""
    has_password = bool(user.password_hash) and user.password_hash.startswith("$2")
    if has_password:
        if not verify_password(req.old_password or "", user.password_hash):
            raise BizError(40003, "原密码不正确")
        if req.old_password == req.new_password:
            raise BizError(40004, "新密码不能与原密码相同")
    user.password_hash = hash_password(req.new_password)
    _add_security_event(
        db,
        user.id,
        "password_change",
        "修改了登录密码" if has_password else "首次设置了登录密码",
    )
    db.add(user)
    db.commit()
    return ok(message="密码修改成功" if has_password else "密码设置成功")


# ---------- M7 头像上传 ----------


@router.put("/user/avatar")
def upload_avatar(
    req: AvatarUploadReq,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    request: Request = None,
):
    """头像上传：接受 data URL，直接存库（企业演示轻量方案）。"""
    data_url = req.data_url.strip()
    if not data_url.startswith("data:image/") or ";base64," not in data_url:
        raise BizError(40010, "头像格式必须为图片 data URL")
    if len(data_url) > 1_500_000:
        raise BizError(40011, "头像图片过大（超过 1.5MB）")
    user.avatar = data_url
    _add_security_event(db, user.id, "avatar_change", "更新了头像", ip=_client_ip(request))
    db.add(user)
    db.commit()
    return ok(data=_profile_of(user, db), message="头像已更新")


# ---------- M7 双因素认证（TOTP） ----------


@router.post("/user/2fa/setup")
def totp_setup(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """生成 TOTP 密钥与绑定 URI（二维码）。"""
    secret = user.totp_secret or generate_secret()
    user.totp_secret = secret
    db.add(user)
    db.commit()
    return ok(data=TotpSetupResp(secret=secret, otpauth_url=otpauth_url(secret, user.email)).model_dump())


@router.post("/user/2fa/enable")
def totp_enable(
    req: TotpEnableReq,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    request: Request = None,
):
    """校验动态码并开启 2FA。"""
    if not user.totp_secret:
        raise BizError(40012, "请先获取 TOTP 密钥")
    if not verify_totp(user.totp_secret, req.code):
        raise BizError(40013, "动态验证码不正确")
    user.totp_enabled = True
    _add_security_event(db, user.id, "2fa_enable", "开启了双因素认证", ip=_client_ip(request))
    db.add(user)
    db.commit()
    return ok(data=_profile_of(user, db), message="双因素认证已开启")


@router.post("/user/2fa/disable")
def totp_disable(
    req: TotpDisableReq,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    request: Request = None,
):
    """校验动态码并关闭 2FA。"""
    if not user.totp_enabled:
        raise BizError(40014, "当前未开启双因素认证")
    if not verify_totp(user.totp_secret or "", req.code):
        raise BizError(40013, "动态验证码不正确")
    user.totp_enabled = False
    _add_security_event(db, user.id, "2fa_disable", "关闭了双因素认证", ip=_client_ip(request))
    db.add(user)
    db.commit()
    return ok(data=_profile_of(user, db), message="双因素认证已关闭")


# ---------- M7 账号安全事件 ----------


@router.get("/user/security-events")
def security_events(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 50,
):
    """账号安全事件列表（最近 N 条）。"""
    rows = (
        db.query(SecurityEvent)
        .filter(SecurityEvent.user_id == user.id)
        .order_by(SecurityEvent.id.desc())
        .limit(min(max(limit, 1), 200))
        .all()
    )
    return ok(data=[_security_event_resp(e).model_dump(mode="json") for e in rows])
