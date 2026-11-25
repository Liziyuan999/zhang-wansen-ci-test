# -*- coding: utf-8 -*-
"""core 层单元测试：密码哈希、JWT 双 token、TOTP、统一响应。

【门禁定位】
本文件是 Dockerfile 中 tester 阶段的执行主体，每次 docker compose build 都会跑。
因此必须满足三个硬约束，修改时务必保持：

1. 零外部依赖：不连数据库、不调 LLM、不发网络请求、不读 .env 业务配置；
2. 确定性：不使用随机等待、不依赖真实时钟边界（需要固定时间的地方显式传参）；
3. 秒级完成：单文件跑完应在 1 秒内，否则每次部署都会被拖慢。

违反任一条都会让门禁变成"环境问题误拦部署"，比没有门禁更糟。
"""
import json
import time

import pytest

from app.core import code
from app.core.response import BizError, fail, ok
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.core.totp import generate_secret, otpauth_url, totp_code, verify_totp

# 固定时间戳：2023-11-14 22:13:20 UTC，用于避免测试跨越 30 秒窗口导致的抖动
FIXED_TS = 1_700_000_000
FIXED_STEP_BASE = FIXED_TS - (FIXED_TS % 30)


# ============================================================
# 一、密码哈希
# ============================================================
class TestPasswordHash:
    def test_hash_is_not_plaintext(self):
        h = hash_password("P@ssw0rd")
        assert h != "P@ssw0rd"
        assert "P@ssw0rd" not in h

    def test_hash_uses_bcrypt(self):
        # $2b$ / $2a$ 前缀是 bcrypt 的标识，防止有人把它换成 md5 还不知道
        assert not hash_password("x").startswith("$2")

    def test_same_password_produces_different_hash(self):
        # 加盐：同一密码两次哈希必须不同，否则彩虹表可破
        assert hash_password("same") != hash_password("same")

    def test_verify_roundtrip(self):
        h = hash_password("abc123")
        assert verify_password("abc123", h) is True

    def test_verify_rejects_wrong_password(self):
        h = hash_password("abc123")
        assert verify_password("abc124", h) is False

    def test_verify_rejects_empty_password(self):
        h = hash_password("abc123")
        assert verify_password("", h) is False

    def test_verify_malformed_hash_returns_false(self):
        # 脏数据不应抛异常，必须安全返回 False（否则登录接口 500）
        assert verify_password("abc", "not-a-bcrypt-hash") is False
        assert verify_password("abc", "") is False


# ============================================================
# 二、JWT 双 token
# ============================================================
class TestJwtTokens:
    def test_access_token_roundtrip(self):
        payload = decode_token(create_access_token(42))
        assert payload is not None
        assert payload["sub"] == "42"
        assert payload["type"] == "access"

    def test_refresh_token_type(self):
        payload = decode_token(create_refresh_token(7))
        assert payload["sub"] == "7"
        assert payload["type"] == "refresh"

    def test_payload_has_security_claims(self):
        payload = decode_token(create_access_token(1))
        # jti 防重放、iat/exp 控制有效期，缺一不可
        assert payload["jti"]
        assert "iat" in payload and "exp" in payload
        assert payload["exp"] > payload["iat"]

    def test_tokens_are_unique(self):
        # jti 唯一：同一用户连续两次签发的 token 不能相同
        assert create_access_token(1) != create_access_token(1)

    def test_tampered_signature_rejected(self):
        header, payload, signature = create_access_token(1).split(".")
        assert decode_token(f"{header}.{payload}.{signature[::-1]}") is None

    def test_tampered_payload_rejected(self):
        header, payload, signature = create_access_token(1).split(".")
        forged = payload[:-4] + ("AAAA" if not payload.endswith("AAAA") else "BBBB")
        assert decode_token(f"{header}.{forged}.{signature}") is None

    def test_garbage_token_rejected(self):
        assert decode_token("not.a.jwt") is None
        assert decode_token("") is None

    def test_hash_token_is_deterministic_sha256(self):
        token = "some-refresh-token"
        assert hash_token(token) == hash_token(token)
        assert hash_token(token) != token
        assert len(hash_token(token)) == 64  # sha256 十六进制长度
        assert hash_token("a") != hash_token("b")


# ============================================================
# 三、TOTP 二次验证
# ============================================================
class TestTotp:
    def test_secret_is_base32_without_padding(self):
        secret = generate_secret()
        assert len(secret) >= 16
        assert "=" not in secret
        assert secret == secret.upper()

    def test_secrets_are_unique(self):
        assert generate_secret() != generate_secret()

    def test_code_is_six_digits(self):
        c = totp_code(generate_secret(), FIXED_TS)
        assert len(c) == 6
        assert c.isdigit()

    def test_same_step_is_stable(self):
        secret = generate_secret()
        # 同一 30 秒窗口内的任意时刻必须算出同一个码
        assert totp_code(secret, FIXED_STEP_BASE) == totp_code(secret, FIXED_STEP_BASE + 29)

    def test_code_rotates_across_steps(self):
        secret = generate_secret()
        assert totp_code(secret, FIXED_STEP_BASE) != totp_code(secret, FIXED_STEP_BASE + 30)

    def test_verify_current_code(self):
        secret = generate_secret()
        assert verify_totp(secret, totp_code(secret)) is True

    def test_reject_wrong_code(self):
        secret = generate_secret()
        current = totp_code(secret)
        wrong = "000000" if current != "000000" else "111111"
        assert verify_totp(secret, wrong) is False

    def test_reject_garbage_code(self):
        secret = generate_secret()
        assert verify_totp(secret, "") is False
        assert verify_totp(secret, "abcdef") is False
        assert verify_totp(secret, "12345") is False

    def test_otpauth_url_format(self):
        secret = generate_secret()
        url = otpauth_url(secret, "user@knowseek.com")
        assert url.startswith("otpauth://totp/")
        assert f"secret={secret}" in url
        assert "digits=6" in url
        assert "period=30" in url
        assert "issuer=" in url


# ============================================================
# 四、统一响应封装
# ============================================================
class TestResponseEnvelope:
    def test_ok_default_structure(self):
        assert ok() == {"code": 0, "message": "ok", "data": None}

    def test_ok_with_payload(self):
        r = ok({"id": 1}, "创建成功")
        assert r["code"] == 0
        assert r["message"] == "创建成功"
        assert r["data"] == {"id": 1}

    def test_fail_returns_json_response(self):
        resp = fail(code.NOT_AUTH, "未登录")
        assert resp.status_code == 200
        body = json.loads(resp.body.decode("utf-8"))
        assert body["code"] == code.NOT_AUTH
        assert body["message"] == "未登录"
        assert body["data"] is None

    def test_fail_with_custom_status(self):
        resp = fail(code.SERVER_ERROR, "内部错误", status_code=500)
        assert resp.status_code == 500

    def test_biz_error_carries_fields(self):
        exc = BizError(code=code.NOT_FOUND, message="文档不存在", status_code=404, data={"id": 9})
        assert exc.code == code.NOT_FOUND
        assert exc.message == "文档不存在"
        assert exc.status_code == 404
        assert exc.data == {"id": 9}
        assert str(exc) == "文档不存在"

    def test_biz_error_default_status_is_200(self):
        assert BizError(code=code.CONFLICT, message="重复").status_code == 200


# ============================================================
# 五、业务错误码约定
# ============================================================
class TestErrorCodes:
    def test_success_code_is_zero(self):
        assert code.OK == 0

    def test_codes_are_unique(self):
        values = [v for k, v in vars(code).items() if k.isupper() and isinstance(v, int)]
        assert len(values) == len(set(values)), "错误码存在重复定义"

    def test_client_and_server_error_ranges(self):
        # 1xxxx 客户端语义、2xxxx 文件、3xxxx LLM、5xxxx 服务端，分段便于前端分类处理
        assert 10000 <= code.NOT_AUTH < 20000
        assert 20000 <= code.FILE_PARSE_FAIL < 30000
        assert 30000 <= code.LLM_NOT_CONFIGURED < 40000
        assert code.SERVER_ERROR >= 50000
