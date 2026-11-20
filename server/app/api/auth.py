# -*- coding: utf-8 -*-
"""认证接口：QQ 邮箱验证码注册/登录、JWT 双 token 刷新。"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.code import CODE_ERROR, NOT_AUTH, PASSWORD_NOT_SET, SEND_TOO_FREQUENT
from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.core.rate_limit import login_throttle, register_limiter, send_code_limiter
from app.core.response import BizError, ok
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.core.totp import verify_totp
from app.models import Department, RefreshToken, SecurityEvent, User
from app.schemas.auth import (
    ForgotPasswordReq,
    LockStatusReq,
    LoginReq,
    LogoutReq,
    RegisterReq,
    RefreshReq,
    ResetPasswordReq,
    SendCodeReq,
    TokenData,
    UnlockReq,
    UserInfo,
)
from app.services.audit import record_audit
from app.services.email import send_verification_code, verify_code
from app.services.login_security import (
    check_lock,
    record_login_fail,
    record_login_success,
    remaining_lock_seconds,
    unlock_user,
)

router = APIRouter(prefix="/api/auth", tags=["认证"])


def _to_user_info(user: User, dept_name: str | None = None) -> UserInfo:
    return UserInfo(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        status=user.status,
        dept_id=user.dept_id,
        dept_name=dept_name,
        avatar=user.avatar,
        totp_enabled=user.totp_enabled,
        has_password=_has_valid_password(user),
        last_login_time=user.last_login_time,
    )


def _has_valid_password(user: User) -> bool:
    """是否为有效 bcrypt 密码哈希（老用户占位符如 'x' 视为未设置密码）。"""
    return bool(user.password_hash) and user.password_hash.startswith("$2")


# ===== 逐行注释：JWT 双 token 签发（登录/注册/刷新共用的核心函数） =====
# 1. create_access_token(user.id)：签发短期访问令牌（默认有效期 ACCESS_TOKEN_EXPIRE_MINUTES，
#    携带于后续请求的 Authorization: Bearer 头，由依赖 get_current_user 解析校验）。
# 2. create_refresh_token(user.id)：签发长期刷新令牌（默认有效期 REFRESH_TOKEN_EXPIRE_DAYS 天），
#    仅用于 /auth/refresh 换取新的双 token，不参与业务接口鉴权。
# 3. RefreshToken 记录：以 hash_token(refresh_token) 的哈希值入库（不存明文，防库泄露盗用），
#    并记录过期时间；该行记录是服务端"可撤销"能力的来源（logout / refresh 轮换时置 revoked=True）。
# 4. db.commit()：先持久化刷新令牌记录再返回，保证刷新接口能查到这条 token。
# 5. 返回 TokenData(access_token, refresh_token, user)：前端 userStore.setTokens 一次落库三件套。
def _issue_tokens(db: Session, user: User) -> TokenData:
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(refresh_token),
            expires_at=datetime.now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    db.commit()
    dept = db.get(Department, user.dept_id)
    return TokenData(
        access_token=access_token,
        refresh_token=refresh_token,
        user=_to_user_info(user, dept.dept_name if dept else None),
    )


@router.post("/send-code")
def send_code(req: SendCodeReq, request: Request, db: Session = Depends(get_db)):
    client_ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")
    if not send_code_limiter.allow(f"ip:{client_ip}", settings.SEND_CODE_IP_LIMIT_PER_HOUR, 3600):
        raise BizError(SEND_TOO_FREQUENT, "发送过于频繁，请稍后再试")
    if not send_code_limiter.allow(f"email:{req.email}", settings.SEND_CODE_EMAIL_LIMIT_PER_DAY, 86400):
        raise BizError(SEND_TOO_FREQUENT, "该邮箱今日发送次数已达上限")
    send_verification_code(db, req.email, req.purpose)
    return ok(message="验证码已发送，请查收邮箱")


@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordReq, db: Session = Depends(get_db)):
    """找回密码：发送 reset 用途验证码（邮箱不存在也返回成功，避免枚举）。"""
    user = db.query(User).filter(User.email == req.email).first()
    if user:
        send_verification_code(db, req.email, "reset")
    return ok(message="如该邮箱已注册，验证码已发送，请查收邮箱")


@router.post("/reset-password")
def reset_password(req: ResetPasswordReq, db: Session = Depends(get_db)):
    """重置密码：校验 reset 验证码后设置新密码。"""
    user = db.query(User).filter(User.email == req.email).first()
    if not user:
        raise BizError(CODE_ERROR, "邮箱或验证码错误")
    verify_code(db, req.email, "reset", req.code)
    user.password_hash = hash_password(req.new_password)
    db.commit()
    record_audit(db, user, "reset_password", "auth", detail="通过找回密码重置登录密码", ip="")
    return ok(message="密码已重置，请使用新密码登录")


@router.get("/sso-config")
def sso_config():
    """企业 SSO/OAuth 入口预留：返回各渠道接入状态与配置占位，启用需管理员配置。"""
    configs = [
        {
            "provider": "dingtalk",
            "name": "钉钉",
            "enabled": False,
            "configured": False,
            "hint": "预留接入位：配置 ClientId / ClientSecret / AgentId 后可启用钉钉扫码登录",
        },
        {
            "provider": "wecom",
            "name": "企业微信",
            "enabled": False,
            "configured": False,
            "hint": "预留接入位：配置 CorpId / AgentId / Secret 后可启用企业微信扫码登录",
        },
        {
            "provider": "ldap",
            "name": "LDAP / AD",
            "enabled": False,
            "configured": False,
            "hint": "预留接入位：配置 Server / BaseDN / BindDN 后可对接企业目录账号登录",
        },
    ]
    return ok(data=configs, message="SSO 配置读取成功")


# ===== 逐行注释：注册即登录（首次签发双 token） =====
# 1. 入口：register 接收邮箱/密码/姓名/部门/验证码，先校验验证码（send_code 的 register 用途）
#    与邮箱唯一性；dept_id 合法则创建 User（默认 active 状态）。
# 2. 密码安全：password_hash 使用安全哈希存储，绝不落明文；数据库行通过 last_login_at 记录。
# 3. 注册成功后直接走 _issue_tokens 签发 access + refresh 双 token——
#    与 login 保持同一签发链路，前端无需注册后再登录。
# 4. 安全记录：写审计与安全事件（audit/security_event），首次登录 IP 记入常用登录地。
@router.post("/register")
def register(req: RegisterReq, request: Request, db: Session = Depends(get_db)):
    client_ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")
    if not register_limiter.allow(f"reg-ip:{client_ip}", 5, 3600):
        raise BizError(SEND_TOO_FREQUENT, "注册操作过于频繁，请稍后再试")
    if not register_limiter.allow(f"reg-email:{req.email}", 5, 86400):
        raise BizError(SEND_TOO_FREQUENT, "该邮箱注册次数已达上限，请明日再试")
    verify_code(db, req.email, "register", req.code)
    if db.query(User).filter(User.email == req.email).first():
        raise BizError(CODE_ERROR, "该邮箱已注册")
    dept = db.query(Department).filter(Department.dept_name == req.dept_name, Department.parent_id.is_(None)).first()
    if not dept:
        dept = Department(dept_name=req.dept_name, parent_id=None)
        db.add(dept)
        db.flush()
    user = User(
        username=req.username,
        email=req.email,
        password_hash=hash_password(req.password),
        role="staff",
        dept_id=dept.id,
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    tokens = _issue_tokens(db, user)
    return ok(data=tokens, message="注册成功")


# ===== 逐行注释：登录路由（双模式：密码 / 邮箱验证码） =====
# 1. 取客户端真实 IP（优先 x-forwarded-for，反代场景），供登录失败计数与异地告警使用。
# 2. check_lock：登录前先查持久化锁定状态，锁定中直接拒绝并返回剩余秒数（retry_after_seconds）。
# 3. mode == "password"：bcrypt 校验密码；老用户占位哈希（非 $2 开头）视为未设密码，
#    提示转验证码登录；失败走 record_login_fail 计数，触顶即锁定。
# 4. mode 其他（默认 code）：校验邮箱验证码；账号不存在或验证码错误同样计数失败（防枚举）。
# 5. 账号 status != "active"：禁止登录（管理员禁用后立即生效）。
# 6. record_login_success：复位失败计数、更新 last_login_time、做异地登录告警判定。
# 7. _issue_tokens：签发双 token 并持久化 refresh token；record_audit 写登录审计日志。
@router.post("/login")
def login(req: LoginReq, request: Request, db: Session = Depends(get_db)):
    client_ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")
    user = db.query(User).filter(User.email == req.email).first()
    # 登录锁定（持久化）：连续失败 LOGIN_MAX_FAILS 次后锁定 LOGIN_LOCK_MINUTES 分钟
    remain = check_lock(user)
    if remain > 0:
        minutes = max(1, (remain + 59) // 60)
        raise BizError(
            SEND_TOO_FREQUENT,
            f"连续登录失败次数过多，账号已锁定，请 {minutes} 分钟后重试或验证码解锁",
            data={"retry_after_seconds": remain, "locked": True},
        )
    if req.mode == "password":
        # 密码登录：邮箱 + 密码 bcrypt 校验；未设置密码的老用户给出引导
        has_password = user is not None and _has_valid_password(user)
        if not user or not has_password or not verify_password(req.password or "", user.password_hash):
            remain_left = record_login_fail(db, user)
            if remain_left <= 0:
                raise BizError(
                    SEND_TOO_FREQUENT,
                    f"连续登录失败达到 {settings.LOGIN_MAX_FAILS} 次，账号已锁定 {settings.LOGIN_LOCK_MINUTES} 分钟",
                    data={"retry_after_seconds": settings.LOGIN_LOCK_MINUTES * 60, "locked": True},
                )
            if user and not has_password:
                raise BizError(PASSWORD_NOT_SET, "该账号尚未设置密码，请使用验证码登录或找回密码")
            raise BizError(CODE_ERROR, f"邮箱或密码错误（剩余尝试次数 {remain_left}）")
    else:
        # 验证码登录
        if not user:
            record_login_fail(db, user)
            raise BizError(CODE_ERROR, "邮箱或验证码错误，请重新获取验证码")
        try:
            verify_code(db, req.email, "login", req.code)
        except BizError:
            remain_left = record_login_fail(db, user)
            if remain_left <= 0:
                raise BizError(
                    SEND_TOO_FREQUENT,
                    f"连续登录失败达到 {settings.LOGIN_MAX_FAILS} 次，账号已锁定 {settings.LOGIN_LOCK_MINUTES} 分钟",
                    data={"retry_after_seconds": settings.LOGIN_LOCK_MINUTES * 60, "locked": True},
                )
            raise
    if user.status != "active":
        raise BizError(NOT_AUTH, "账号已被禁用")
    # 修复 P1-1：双因素认证（TOTP）强制校验。
    # 此前 totp_enabled 仅在 /user/2fa/* 中维护，登录流程完全没有校验，开启 2FA 等于无效。
    # 规则：开启 2FA 的账号必须携带正确动态码；未开启的账号完全不受影响。
    if getattr(user, "totp_enabled", False):
        totp_code = (req.totp_code or "").strip()
        if not totp_code:
            raise BizError(
                CODE_ERROR,
                "该账号已开启双因素认证，请输入动态验证码后登录",
                data={"need_totp": True},
            )
        if not verify_totp(user.totp_secret or "", totp_code):
            remain_left = record_login_fail(db, user)
            if remain_left <= 0:
                raise BizError(
                    SEND_TOO_FREQUENT,
                    f"连续登录失败达到 {settings.LOGIN_MAX_FAILS} 次，账号已锁定 {settings.LOGIN_LOCK_MINUTES} 分钟",
                    data={"retry_after_seconds": settings.LOGIN_LOCK_MINUTES * 60, "locked": True, "need_totp": True},
                )
            raise BizError(CODE_ERROR, f"动态验证码不正确（剩余尝试次数 {remain_left}）", data={"need_totp": True})
    # 登录成功：复位失败计数、写安全事件、异地登录告警判定
    record_login_success(db, user, client_ip)
    tokens = _issue_tokens(db, user)
    record_audit(db, user, "login", "auth", detail="用户登录成功", ip=client_ip)
    return ok(data=tokens, message="登录成功")


@router.post("/lock-status")
def lock_status(req: LockStatusReq, db: Session = Depends(get_db)):
    """查询账号登录锁定状态（无需登录态，供登录页展示锁定提示）。"""
    user = db.query(User).filter(User.email == req.email).first()
    remain = remaining_lock_seconds(user)
    fail_count = (user.login_fail_count or 0) if user else 0
    return ok(
        data={
            "locked": remain > 0,
            "retry_after_seconds": remain,
            "fail_count": fail_count,
            "max_fails": settings.LOGIN_MAX_FAILS,
            "lock_minutes": settings.LOGIN_LOCK_MINUTES,
        },
        message="查询成功",
    )


@router.post("/unlock")
def unlock(req: UnlockReq, db: Session = Depends(get_db)):
    """账号解锁（自助）：校验邮箱验证码后解除锁定并复位失败计数。"""
    user = db.query(User).filter(User.email == req.email).first()
    if not user:
        raise BizError(CODE_ERROR, "邮箱不存在")
    if remaining_lock_seconds(user) <= 0:
        return ok(message="账号当前未锁定")
    verify_code(db, req.email, "unlock", req.code)
    unlock_user(db, user, operator=user, via="code")
    return ok(message="账号已解锁，请重新登录")


# ===== 逐行注释：刷新 token 路由（access 过期后用 refresh 换取新双 token） =====
# 1. decode_token：解析 refresh token 的 JWT 载荷；无效或 type != "refresh" 直接 401。
# 2. 查 refresh_token 表：按 hash_token(refresh_token) 精确匹配，且 revoked=False；
#    查不到或已过期（expires_at < now）说明 token 已被撤销/轮换过，返回 401。
# 3. 旋转（rotation）：将旧 refresh token 置 revoked=True 再签发新 token——被盗的旧 token
#    一旦被使用即失效，符合 OAuth2 refresh token 轮换最佳实践。
# 4. 再次校验用户：sub 中用户必须存在且 status == "active"（被禁用后刷新立即失效）。
# 5. 复用 _issue_tokens 签发新双 token 并持久化新 refresh 记录。
@router.post("/refresh")
def refresh(req: RefreshReq, db: Session = Depends(get_db)):
    payload = decode_token(req.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise BizError(NOT_AUTH, "刷新 token 无效", status_code=401)
    row = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == hash_token(req.refresh_token), RefreshToken.revoked.is_(False))
        .first()
    )
    if not row or row.expires_at < datetime.now():
        raise BizError(NOT_AUTH, "刷新 token 已过期或已失效", status_code=401)
    row.revoked = True
    db.commit()
    user = db.get(User, int(payload["sub"]))
    if not user or user.status != "active":
        raise BizError(NOT_AUTH, "用户不存在或已禁用", status_code=401)
    tokens = _issue_tokens(db, user)
    return ok(data=tokens, message="刷新成功")


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    dept = db.get(Department, user.dept_id)
    return ok(data=_to_user_info(user, dept.dept_name if dept else None))


# ===== 逐行注释：退出登录（服务端撤销指定 refresh token） =====
# 1. 依赖 get_current_user 校验 access token：未登录（token 无效/过期）直接 401，拒绝"假装退出"。
# 2. 按 user_id + hash_token(refresh_token) 精确匹配未撤销记录：只撤销当前账号的该条 token，
#    不影响同一账号在其他设备上已签发的其他 refresh token。
# 3. 命中则置 revoked=True 并提交：refresh 接口将拒绝该 token（无法再续期），实现真正登出；
#    未命中（已撤销/过期）静默返回成功，幂等设计。
@router.post("/logout")
def logout(req: LogoutReq, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """注销：撤销当前用户的指定 refresh token（服务端立即失效）。"""
    row = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.user_id == user.id,
            RefreshToken.token_hash == hash_token(req.refresh_token),
            RefreshToken.revoked.is_(False),
        )
        .first()
    )
    if row:
        row.revoked = True
        db.commit()
    return ok(message="已退出登录")
