# -*- coding: utf-8 -*-
"""QQ 邮箱验证码服务：发送、生成、校验。"""
import hashlib
import logging
import random
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText

from sqlalchemy.orm import Session

from app.core.code import CODE_ERROR, EMAIL_REGISTERED, SEND_TOO_FREQUENT
from app.core.config import settings
from app.core.response import BizError
from app.models import EmailCode, User

logger = logging.getLogger(__name__)


def _hash_code(code: str) -> str:
    return hashlib.sha256((settings.JWT_SECRET + code).encode("utf-8")).hexdigest()


def generate_code() -> str:
    return f"{random.randint(0, 999999):06d}"


def check_send_interval(db: Session, email: str, purpose: str) -> None:
    last = (
        db.query(EmailCode)
        .filter(EmailCode.email == email, EmailCode.purpose == purpose)
        .order_by(EmailCode.create_time.desc())
        .first()
    )
    if last:
        interval = (datetime.now() - last.create_time).total_seconds()
        if interval < settings.EMAIL_SEND_INTERVAL_SECONDS:
            remain = int(settings.EMAIL_SEND_INTERVAL_SECONDS - interval)
            raise BizError(SEND_TOO_FREQUENT, f"发送过于频繁，请 {remain} 秒后重试")


def send_verification_code(db: Session, email: str, purpose: str) -> None:
    check_send_interval(db, email, purpose)
    if purpose == "register" and db.query(User).filter(User.email == email).first():
        raise BizError(EMAIL_REGISTERED, "该邮箱已注册，请直接登录")

    code = generate_code()
    expires_at = datetime.now() + timedelta(minutes=settings.EMAIL_CODE_EXPIRE_MINUTES)
    db.add(EmailCode(email=email, purpose=purpose, code_hash=_hash_code(code), expires_at=expires_at, used=False))
    db.commit()

    if not settings.MAIL_USER:
        logger.info("[模拟发送验证码] %s purpose=%s", email, purpose)
        if settings.DEV_PRINT_CODE:
            print(f"[DEV] 验证码邮件(未配置SMTP，模拟发送): {email} code={code}")
        return

    body = f"【知寻 KnowSeek】您的验证码为 {code}，{settings.EMAIL_CODE_EXPIRE_MINUTES} 分钟内有效。若非本人操作请忽略。"
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = "知寻 KnowSeek 验证码"
    msg["From"] = settings.MAIL_FROM or settings.MAIL_USER
    msg["To"] = email
    try:
        with smtplib.SMTP_SSL(settings.MAIL_HOST, settings.MAIL_PORT, timeout=15) as server:
            server.login(settings.MAIL_USER, settings.MAIL_PASS)
            server.sendmail(msg["From"], [email], msg.as_string())
        logger.info("验证码已发送至 %s", email)
    except Exception as exc:  # 发送失败不应阻塞注册流程演示
        logger.warning("邮件发送失败: %s", exc)
        if settings.DEV_PRINT_CODE:
            print(f"[DEV] 邮件发送失败，验证码已入库: {email} code={code}")


def verify_code(db: Session, email: str, purpose: str, code: str) -> None:
    record = (
        db.query(EmailCode)
        .filter(EmailCode.email == email, EmailCode.purpose == purpose, EmailCode.used.is_(False))
        .order_by(EmailCode.create_time.desc())
        .first()
    )
    if not record or record.expires_at < datetime.now() or record.code_hash != _hash_code(code):
        raise BizError(CODE_ERROR, "验证码错误或已过期，请重新获取验证码")
    record.used = True
    db.commit()


def send_invitation_email(to_email: str, team_name: str, inviter_name: str, accept_url: str) -> None:
    """发送团队邀请邮件（复用 QQ 邮箱 SMTP 配置；未配置 SMTP 时模拟发送）。"""
    if not settings.MAIL_USER:
        logger.info("[模拟发送团队邀请] %s team=%s", to_email, team_name)
        if settings.DEV_PRINT_CODE:
            print(f"[DEV] 团队邀请邮件(未配置SMTP，模拟发送): {to_email} url={accept_url}")
        return

    body = (
        f"【知寻 KnowSeek】{inviter_name} 邀请您加入团队「{team_name}」。\n"
        f"点击以下链接接受邀请（48 小时内有效）：\n{accept_url}\n"
        f"若非本人操作请忽略。"
    )
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = "知寻 KnowSeek 团队邀请"
    msg["From"] = settings.MAIL_FROM or settings.MAIL_USER
    msg["To"] = to_email
    try:
        with smtplib.SMTP_SSL(settings.MAIL_HOST, settings.MAIL_PORT, timeout=15) as server:
            server.login(settings.MAIL_USER, settings.MAIL_PASS)
            server.sendmail(msg["From"], [to_email], msg.as_string())
        logger.info("团队邀请邮件已发送至 %s", to_email)
    except Exception as exc:  # 发送失败不应阻塞邀请流程演示
        logger.warning("团队邀请邮件发送失败: %s", exc)
        if settings.DEV_PRINT_CODE:
            print(f"[DEV] 团队邀请邮件发送失败: {to_email} url={accept_url}")
