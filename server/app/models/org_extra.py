# -*- coding: utf-8 -*-
"""组织中心扩展模型：共享知识库下载审批 / 退出团队审批 / 企业打卡。"""
# ===== 逐行注释：组织中心扩展数据模型（六张表） =====
# 1. DownloadApproval：共享知识库文档下载审批（成员申请 -> 所有者/管理员审批 -> 通过后下载），
#    status 状态机 pending/approved/rejected，reminder_sent_at 防重复超时催办。
# 2. TeamExitApproval：成员退出团队审批（申请 -> 审批 -> 通过后自动移除成员），结构同上。
# 3. AttendanceRecord：企业打卡，每成员每天一条，四段班次（am_in/am_out/pm_in/pm_out），
#    clock_in/clock_out 为兼容旧字段（等价 am_in/pm_out）；checkin_meta 存每段定位与设备
#    审计信息（JSON 字符串，防篡改溯源）；UniqueConstraint 保证同人同天仅一条。
# 4. TeamRole：自定义角色 + 权限矩阵（perms 存权限点 key 列表）；role_key 形如 custom_{id}，
#    built_in 标记内置角色（owner/admin/member，仅展示不可编辑删除）。
# 5. TeamGeoConfig：团队工作区域地理围栏（中心点 lat/lng + 半径 radius_m），
#    开启后成员打卡必须位于围栏内（enabled 开关 + updater_id 记录配置人）。
# 6. AttendanceFixApproval：考勤补卡审批（slot 对应班次 am_in/am_out/pm_in/pm_out），
#    审批通过后按审批时间修正打卡记录并写审计，实现留痕可溯源。
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DownloadApproval(Base):
    """共享知识库文档下载审批：成员申请下载 -> 所有者/管理员审批 -> 通过后下载。"""

    __tablename__ = "download_approval"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("team.id"), nullable=False)
    doc_id: Mapped[int] = mapped_column(Integer, ForeignKey("document.id"), nullable=False)
    applicant_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    approver_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("user.id"), nullable=True)
    reason: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/approved/rejected
    reject_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    apply_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    handle_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # 超时催办时间（防重复催办）


class TeamExitApproval(Base):
    """成员退出团队审批：成员申请 -> 所有者/管理员审批 -> 通过后自动移除成员。"""

    __tablename__ = "team_exit_approval"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("team.id"), nullable=False)
    applicant_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    approver_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("user.id"), nullable=True)
    reason: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/approved/rejected
    reject_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    apply_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    handle_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # 超时催办时间（防重复催办）


class AttendanceRecord(Base):
    """企业打卡：每成员每天一条，四段班次（上午上班/上午下班/下午上班/下午下班）。

    clock_in_time / clock_out_time 为兼容旧字段，等价于 am_in_time / pm_out_time；
    checkin_meta 记录每段打卡的定位与设备审计信息（JSON 字符串），防篡改溯源。
    """

    __tablename__ = "attendance_record"
    __table_args__ = (UniqueConstraint("team_id", "user_id", "date", name="uq_attendance_team_user_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("team.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    date: Mapped[str] = mapped_column(String(16), nullable=False)  # YYYY-MM-DD
    # 四段班次时间（服务端时间，客户端不可传入）
    clock_in_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # 兼容旧字段 = am_in
    clock_out_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # 兼容旧字段 = pm_out
    am_out_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # 上午下班 12:00
    pm_in_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # 下午上班 13:30
    pm_out_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # 下午下班 17:00
    checkin_meta: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON：每段 {lat,lng,ip,ua,ts}
    create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class TeamRole(Base):
    """自定义角色：组织中心可自建角色并配置权限矩阵（perms 存权限点 key 列表）。

    role_key 用于成员 role 字段引用（内置角色 owner/admin/member；自定义角色 key 形如 custom_{id}）。
    built_in=True 表示系统内置角色（仅展示，不可编辑/删除）。
    """

    __tablename__ = "team_role"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("team.id"), nullable=False)
    role_key: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    role_name: Mapped[str] = mapped_column(String(64), nullable=False)
    perms: Mapped[list | None] = mapped_column(JSON, nullable=True)  # 权限点 key 列表
    built_in: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class TeamGeoConfig(Base):
    """团队工作区域（地理围栏）：管理员配置中心点/半径后，成员打卡必须位于围栏内。"""

    __tablename__ = "team_geo_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("team.id"), nullable=False, unique=True)
    lat: Mapped[float] = mapped_column(Float, nullable=False)  # 中心纬度
    lng: Mapped[float] = mapped_column(Float, nullable=False)  # 中心经度
    radius_m: Mapped[int] = mapped_column(Integer, nullable=False, default=500)  # 半径（米）
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    update_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
    updater_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("user.id"), nullable=True)


class AttendanceFixApproval(Base):
    """考勤补卡审批：迟到/漏卡时成员提交补卡申请，管理员审批通过后修正打卡记录。

    slot 取值与打卡班次一致：am_in/am_out/pm_in/pm_out。
    审批通过后系统将对应日期对应班次的打卡时间修正为审批通过时间并写入审计，实现留痕可溯源。
    """

    __tablename__ = "attendance_fix_approval"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("team.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)  # 申请人
    approver_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("user.id"), nullable=True)
    date: Mapped[str] = mapped_column(String(16), nullable=False)  # 补卡日期 YYYY-MM-DD
    slot: Mapped[str] = mapped_column(String(16), nullable=False)  # am_in/am_out/pm_in/pm_out
    reason: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/approved/rejected
    reject_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    apply_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    handle_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # 超时催办时间（防重复催办）
