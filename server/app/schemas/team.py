# -*- coding: utf-8 -*-
"""团队相关请求/响应模型。"""
from pydantic import BaseModel, EmailStr, Field


class CreateTeamReq(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    description: str = Field(default="", max_length=255)


class UpdateTeamReq(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    description: str = Field(default="", max_length=255)


class InviteReq(BaseModel):
    qq_email: EmailStr


class TransferReq(BaseModel):
    target_user_id: int


class MemberResp(BaseModel):
    user_id: int
    username: str
    email: str
    role: str
    joined_at: str | None = None
    perms: list[str] = []


class InvitationResp(BaseModel):
    id: int
    email: str
    status: str
    token: str = ""
    accept_url: str = ""
    inviter_name: str | None = None
    expires_at: str | None = None
    create_time: str | None = None


class UpdateMemberRoleReq(BaseModel):
    role: str = Field(pattern="^(member|admin|owner|custom_\\d+)$", description="目标角色：member/admin/owner 或自定义角色 custom_{id}")


class UpdateMemberPermsReq(BaseModel):
    """细粒度权限位：manage_docs / manage_members / send_notice / view_audit / manage_departments"""
    perms: list[str] = Field(default_factory=list, max_length=16)


class DepartmentNodeResp(BaseModel):
    """组织架构树节点：团队/部门层级视图。"""
    team_id: int
    name: str
    description: str | None = None
    parent_id: int | None = None
    member_count: int = 0
    my_role: str = "member"
    children: list["DepartmentNodeResp"] = []


class SetParentReq(BaseModel):
    parent_id: int | None = Field(default=None, description="上级部门团队 ID；传 None 表示置为顶级部门")


class TeamResp(BaseModel):
    id: int
    name: str
    description: str | None = None
    owner_id: int
    owner_name: str | None = None
    member_count: int = 0
    my_role: str = "member"
    create_time: str | None = None


class TeamDetailResp(TeamResp):
    members: list[MemberResp] = []
    invitations: list[InvitationResp] = []


class InviteInfoResp(BaseModel):
    team_id: int
    team_name: str
    inviter_id: int
    inviter_name: str
    inviter_email: str
    email: str
    status: str
    expires_at: str | None = None


class JoinTeamReq(BaseModel):
    """加入团队：邀请链接或 token 二选一。"""

    token: str = Field(min_length=8, max_length=128, description="邀请 token 或完整邀请链接")


class TeamLogResp(BaseModel):
    id: int
    user_id: int
    username: str
    action: str
    message: str
    create_time: str | None = None
