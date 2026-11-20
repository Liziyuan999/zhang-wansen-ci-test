# -*- coding: utf-8 -*-
"""登录安全服务：登录失败锁定（持久化）+ 异地登录告警。

- 登录锁定：同一账号连续失败 LOGIN_MAX_FAILS 次后锁定 LOGIN_LOCK_MINUTES 分钟，
  锁定状态持久化到 user 表（重启不丢失），支持自助验证码解锁与管理员强制解锁。
- 异地告警：登录 IP 与常用登录 IP 不一致时，向通知中心推送安全告警并写安全事件/审计。
  归属地判定采用"常用登录 IP 集合"离线方案（无需第三方 GeoIP 服务，兼容内网/出口 IP 变化）。
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import SecurityEvent, User, UserNotification
from app.services.audit import record_audit
from app.services.notification_service import notify_user

logger = logging.getLogger(__name__)

_COMMON_IP_MIN_HITS = 2  # 历史登录中同一 IP 出现 >= 2 次视为常用登录地
_HISTORY_LIMIT = 50  # 参与判定的最近登录事件条数


def remaining_lock_seconds(user: User | None) -> int:
    """返回账号剩余锁定秒数（0 表示未锁定）。"""
    if not user or not user.login_locked_until:
        return 0
    remain = (user.login_locked_until - datetime.now()).total_seconds()
    return int(remain) + 1 if remain > 0 else 0


# ===== 逐行注释：登录前锁定检查（含过期自动复位） =====
# 1. remaining_lock_seconds：换算锁定到期剩余秒数，>0 表示仍在锁定窗口内（含 +1 秒向上取整）。
# 2. 仍在锁定期：直接返回剩余秒数，调用方（login 路由）拒绝登录并提示 retry_after_seconds。
# 3. 锁定记录已过期（login_locked_until <= now）：自动复位锁定与失败计数，
#    避免"锁定一次永久锁定"的误伤，用户无需等待也无需解锁操作。
def check_lock(user: User | None) -> int:
    """登录前检查：已锁定返回剩余秒数，否则 0。"""
    remain = remaining_lock_seconds(user)
    if remain > 0:
        return remain
    if user and user.login_locked_until and user.login_locked_until <= datetime.now():
        # 锁定已过期，自动复位
        user.login_locked_until = None
        user.login_fail_count = 0
    return 0


# ===== 逐行注释：记录一次登录失败（持久化锁定策略） =====
# 1. user 为 None（邮箱不存在）：不落任何计数直接返回 LOGIN_MAX_FAILS，避免暴露账号是否存在。
# 2. 正常情况：login_fail_count 自增 1（数据库持久化，重启不丢）。
# 3. 达到阈值 LOGIN_MAX_FAILS：写入 login_locked_until = now + LOGIN_LOCK_MINUTES 分钟，
#    同时追加 SecurityEvent(event_type="login_lock") 安全事件，供审计/安全看板追溯。
# 4. 返回剩余可用次数：>0 时接口继续报"邮箱或密码错误（剩余 N 次）"；=0 表示本次已触发锁定。
def record_login_fail(db: Session, user: User | None) -> int:
    """记录一次登录失败；返回本次失败后剩余可用次数（0 表示已触发锁定）。"""
    if not user:
        return settings.LOGIN_MAX_FAILS
    user.login_fail_count = (user.login_fail_count or 0) + 1
    if user.login_fail_count >= settings.LOGIN_MAX_FAILS:
        user.login_locked_until = datetime.now() + timedelta(minutes=settings.LOGIN_LOCK_MINUTES)
        db.add(
            SecurityEvent(
                user_id=user.id,
                event_type="login_lock",
                description=f"连续登录失败 {settings.LOGIN_MAX_FAILS} 次，账号锁定 {settings.LOGIN_LOCK_MINUTES} 分钟",
            )
        )
        db.commit()
        return 0
    db.commit()
    return settings.LOGIN_MAX_FAILS - user.login_fail_count


# ===== 逐行注释：登录成功处理（复位计数 + 异地告警判定） =====
# 1. 复位：login_fail_count 清零、login_locked_until 置空（登录成功即解除历史锁定）。
# 2. 更新 last_login_time 为当前时间。
# 3. _is_abnormal_ip：基于最近 50 条登录事件判断本次 IP 是否常用登录地；
#    注意必须先于写入本次 login 事件执行——否则事件列表首位恒为本次 IP，异地判定永不触发。
# 4. 写入 event_type="login" 的安全事件（含 IP），供安全看板/审计追溯。
# 5. 异常判定通过时调用 _notify_anomaly 推送通知中心告警。
def record_login_success(db: Session, user: User, ip: str) -> None:
    """登录成功后复位失败计数，并做异地登录告警判定。

    注意：告警判定必须先于写入本次 login 事件执行，
    否则 ips[0] 恒为本次 IP，异地判定永远不触发。
    """
    user.login_fail_count = 0
    user.login_locked_until = None
    user.last_login_time = datetime.now()
    abnormal = bool(ip) and _is_abnormal_ip(db, user, ip)
    db.add(SecurityEvent(user_id=user.id, event_type="login", description="账号登录成功", ip=ip or None))
    db.commit()
    if abnormal:
        _notify_anomaly(db, user, ip)


def unlock_user(db: Session, user: User, operator: User | None = None, via: str = "manual") -> None:
    """解锁账号（via: code=验证码自助 / admin=管理员强制）。"""
    user.login_fail_count = 0
    user.login_locked_until = None
    db.add(SecurityEvent(user_id=user.id, event_type="login_unlock", description=f"账号解锁（{via}）"))
    db.commit()
    record_audit(
        db,
        operator or user,
        "unlock_account",
        "auth",
        f"解锁账号 {user.email}（途径：{'验证码' if via == 'code' else '管理员'}）",
    )


def _is_abnormal_ip(db: Session, user: User, ip: str) -> bool:
    """判断本次登录 IP 是否非常用登录地（无历史或首次登录不告警）。"""
    events = (
        db.query(SecurityEvent.ip)
        .filter(
            SecurityEvent.user_id == user.id,
            SecurityEvent.event_type == "login",
            SecurityEvent.ip.isnot(None),
            SecurityEvent.ip != "",
        )
        .order_by(SecurityEvent.id.desc())
        .limit(_HISTORY_LIMIT)
        .all()
    )
    ips = [e[0] for e in events]
    if not ips:
        return False
    # 本次 IP 若与最近一次一致则视为连续登录同一环境，不告警
    if ips[0] == ip:
        return False
    common = {i for i in ips if ips.count(i) >= _COMMON_IP_MIN_HITS}
    if not common:
        return False
    return ip not in common


def _notify_anomaly(db: Session, user: User, ip: str) -> None:
    """推送异地登录告警（通知中心 system 分类）+ 写安全事件与审计。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    notify_user(
        db,
        user.id,
        "异地登录告警",
        f"您的账号于 {now} 在 IP {ip} 登录，与常用登录地不一致。如非本人操作，请尽快修改密码或联系管理员。",
        category="system",
        ntype="security",
    )
    db.add(
        SecurityEvent(
            user_id=user.id,
            event_type="login_anomaly",
            description=f"异地登录告警：登录 IP {ip} 与常用登录地不一致",
            ip=ip,
        )
    )
    db.commit()
    record_audit(db, user, "login_anomaly", "auth", f"异地登录告警：登录 IP {ip} 与常用登录地不一致")
