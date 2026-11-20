# -*- coding: utf-8 -*-
"""认证相关请求/响应模型。"""
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class SendCodeReq(BaseModel):
    email: EmailStr
    purpose: str = Field("register", pattern="^(register|login|reset|unlock)$")


class RegisterReq(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=8)
    username: str = Field(min_length=2, max_length=32)
    password: str = Field(min_length=6, max_length=64)
    dept_name: str = Field(min_length=1, max_length=32)


class LoginReq(BaseModel):
    """登录请求：双模式自选。

    - mode="code"：验证码登录（原逻辑），必传 code；
    - mode="password"：密码登录，必传 password（code 可空）。
    """
    email: EmailStr
    mode: str = Field(default="code", pattern="^(code|password)$")
    code: str | None = Field(default=None, min_length=4, max_length=8)
    password: str | None = Field(default=None, min_length=6, max_length=64)
    # 修复 P1-1：开启双因素认证（totp_enabled）的账号登录时必须回传 TOTP 动态码；
    # 未开启的用户该字段可为空，不受影响。
    totp_code: str | None = Field(default=None, max_length=8, description="双因素动态码（已开启 2FA 的账号必填）")
    remember: bool = False  # 记住我：延长登录态（由前端决定存储位置）


class ForgotPasswordReq(BaseModel):
    email: EmailStr


class LockStatusReq(BaseModel):
    email: EmailStr


class UnlockReq(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=8)


class ResetPasswordReq(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=8)
    new_password: str = Field(min_length=6, max_length=64)


class RefreshReq(BaseModel):
    refresh_token: str


class LogoutReq(BaseModel):
    refresh_token: str


class DeptInfo(BaseModel):
    id: int
    dept_name: str


class UserInfo(BaseModel):
    id: int
    username: str
    email: str
    role: str
    status: str
    dept_id: int
    dept_name: str | None = None
    avatar: str | None = None
    totp_enabled: bool = False
    has_password: bool = False
    last_login_time: datetime | None = None


class TokenData(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserInfo


class UserProfile(BaseModel):
    """个人中心完整资料。"""
    id: int
    username: str
    email: str
    role: str
    status: str
    dept_id: int
    dept_name: str | None = None
    avatar: str | None = None
    totp_enabled: bool = False
    has_password: bool = False
    last_login_time: datetime | None = None
    create_time: datetime | None = None
    update_time: datetime | None = None


class UpdateProfileReq(BaseModel):
    """更新个人资料（昵称/部门）。"""
    username: str | None = Field(default=None, min_length=2, max_length=32)
    dept_id: int | None = None


class ChangePasswordReq(BaseModel):
    """修改密码；无密码老用户首次设置时可不传原密码。"""
    old_password: str | None = Field(default=None, min_length=6, max_length=64)
    new_password: str = Field(min_length=6, max_length=64)


class AvatarUploadReq(BaseModel):
    """头像上传：data URL（data:image/png;base64,...），大小不超过 1.5MB。"""
    data_url: str = Field(min_length=22, max_length=2_000_000)


class TotpSetupResp(BaseModel):
    secret: str
    otpauth_url: str


class TotpEnableReq(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class TotpDisableReq(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class SecurityEventResp(BaseModel):
    id: int
    event_type: str
    description: str
    ip: str | None = None
    create_time: datetime | None = None
