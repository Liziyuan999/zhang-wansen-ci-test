# -*- coding: utf-8 -*-
"""轻量 TOTP（RFC 6238）实现：不依赖 pyotp，用于双因素认证。"""
import base64
import hashlib
import hmac
import os
import struct
import time

_STEP = 30
_DIGITS = 6


def generate_secret() -> str:
    """生成 32 字符 Base32 随机密钥（secret 长度 20 字节）。"""
    return base64.b32encode(os.urandom(20)).decode("ascii").rstrip("=")


def _base32_decode(secret: str) -> bytes:
    pad = "=" * ((8 - len(secret) % 8) % 8)
    return base64.b32decode(secret.upper() + pad)


def _hotp(secret: bytes, counter: int, digits: int = _DIGITS) -> str:
    msg = struct.pack(">Q", counter)
    digest = hmac.new(secret, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF) % (10**digits)
    return f"{code:0{digits}d}"


def totp_code(secret: str, at: float | None = None) -> str:
    ts = int(time.time()) if at is None else int(at)
    return _hotp(_base32_decode(secret), ts // _STEP)


def verify_totp(secret: str, code: str, window: int = 1) -> bool:
    """校验 TOTP 验证码，允许前后各 window 个时间窗漂移。"""
    code = code.strip()
    if not secret or not code:
        return False
    now = int(time.time())
    for i in range(-window, window + 1):
        if hmac.compare_digest(totp_code(secret, now + i * _STEP), code):
            return True
    return False


def otpauth_url(secret: str, account: str, issuer: str = "知寻 KnowSeek") -> str:
    """生成 otpauth:// URI，供二维码（authenticator 扫码绑定）。"""
    import urllib.parse

    return f"otpauth://totp/{urllib.parse.quote(issuer)}:{urllib.parse.quote(account)}?secret={secret}&issuer={urllib.parse.quote(issuer)}&digits={_DIGITS}&period={_STEP}"
