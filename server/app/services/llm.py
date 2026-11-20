# -*- coding: utf-8 -*-
"""LLM 调用服务：多供应商（OpenAI 兼容接口），支持流式、调用记录与失败回退。

供应商来源优先级：
  1. 显式指定的 provider_id（数据库 model_provider 表，须启用且有 api_key）
  2. 数据库默认供应商（enabled + is_default，且已配置 api_key）
  3. 环境变量（settings.DEEPSEEK_API_KEY / LLM_MODEL / LLM_BASE_URL，保留兜底）

调用失败按上述顺序自动回退下一个候选，全部失败才抛错。
"""
import asyncio
import json
import logging
import time
from typing import Any, Callable

import httpx

from app.core.code import LLM_NOT_CONFIGURED
from app.core.config import settings
from app.core.response import BizError
from app.models import LlmCallLog, ModelProvider

logger = logging.getLogger(__name__)


def _count_tokens(text: str) -> int:
    # 简单估算：中文按字符、英文按单词
    if not text:
        return 0
    cn = len([c for c in text if "\u4e00" <= c <= "\u9fff"])
    en = len(text.replace(" ", "").split())
    return cn + max(1, en // 3)


def _log_call(
    db,
    user_id: int,
    scenario: str,
    model_name: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: int,
    is_success: bool,
    error_msg: str | None = None,
) -> None:
    try:
        db.add(
            LlmCallLog(
                user_id=user_id,
                scenario=scenario,
                model_name=model_name,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                latency_ms=latency_ms,
                is_success=is_success,
                error_msg=error_msg,
            )
        )
        db.commit()
    except Exception as exc:  # pragma: no cover
        logger.warning("写入 LLM 调用记录失败: %s", exc)
        db.rollback()


def check_llm_configured() -> None:
    if not settings.DEEPSEEK_API_KEY:
        raise BizError(LLM_NOT_CONFIGURED, "LLM 未配置 DEEPSEEK_API_KEY，请在 .env 中设置")


# ---------------------------------------------------------------------------
# 供应商查询与路由
# ---------------------------------------------------------------------------


def get_llm_providers(db, only_enabled: bool = True) -> list[ModelProvider]:
    """查询可用供应商（仅返回已启用且已配置 api_key 的，供前端模型选择）。"""
    q = db.query(ModelProvider)
    if only_enabled:
        q = q.filter(ModelProvider.enabled.is_(True))
    rows = q.order_by(ModelProvider.is_default.desc(), ModelProvider.id.asc()).all()
    return [p for p in rows if (p.api_key or "").strip()]


def get_default_provider(db) -> ModelProvider | None:
    """默认供应商（enabled + is_default + 已配置 api_key）。"""
    p = (
        db.query(ModelProvider)
        .filter(ModelProvider.enabled.is_(True), ModelProvider.is_default.is_(True))
        .first()
    )
    if p and (p.api_key or "").strip():
        return p
    return None


def _resolve_candidates(db, provider_id: int | None) -> list[ModelProvider | None]:
    """返回候选供应商列表；None 表示环境变量配置（DeepSeek 兜底）。"""
    candidates: list[ModelProvider | None] = []
    seen: set[tuple[str, str]] = set()

    def _append(p: ModelProvider | None) -> None:
        if p is None:
            key = (settings.LLM_BASE_URL.rstrip("/"), settings.LLM_MODEL)
        else:
            key = (p.base_url.rstrip("/"), p.model)
        if key not in seen:
            seen.add(key)
            candidates.append(p)

    if db is not None:
        if provider_id is not None:
            p = db.get(ModelProvider, provider_id)
            if p and p.enabled and (p.api_key or "").strip():
                _append(p)
        default_p = get_default_provider(db)
        if default_p is not None:
            _append(default_p)
    if settings.DEEPSEEK_API_KEY:
        _append(None)
    return candidates


def _endpoint(provider: ModelProvider | None) -> tuple[str, str, str]:
    """返回 (url, model, api_key)。"""
    if provider is None:
        return (
            settings.LLM_BASE_URL.rstrip("/") + "/chat/completions",
            settings.LLM_MODEL,
            settings.DEEPSEEK_API_KEY,
        )
    return (
        provider.base_url.rstrip("/") + "/chat/completions",
        provider.model,
        provider.api_key,
    )


# ---------------------------------------------------------------------------
# 单次调用
# ---------------------------------------------------------------------------


def _call_once(
    db,
    user_id: int,
    provider: ModelProvider | None,
    messages: list[dict[str, str]],
    scenario: str,
    temperature: float,
    max_tokens: int,
    stream_handler: Callable[[str], None] | None,
) -> str:
    url, model_name, api_key = _endpoint(provider)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload: dict[str, Any] = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    start = time.monotonic()
    prompt_tokens = _count_tokens("".join(m.get("content", "") for m in messages))
    try:
        if stream_handler:
            payload["stream"] = True
            collected: list[str] = []
            with httpx.stream("POST", url, headers=headers, json=payload, timeout=settings.LLM_TIMEOUT_SECONDS) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                        delta = obj["choices"][0].get("delta", {}).get("content", "")
                    except Exception:
                        delta = ""
                    if delta:
                        collected.append(delta)
                        stream_handler(delta)
            content = "".join(collected)
        else:
            resp = httpx.post(url, headers=headers, json=payload, timeout=settings.LLM_TIMEOUT_SECONDS)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]

        latency = int((time.monotonic() - start) * 1000)
        completion_tokens = _count_tokens(content)
        _log_call(db, user_id, scenario, model_name, prompt_tokens, completion_tokens, latency, True)
        return content
    except Exception as exc:
        latency = int((time.monotonic() - start) * 1000)
        _log_call(db, user_id, scenario, model_name, prompt_tokens, 0, latency, False, str(exc))
        logger.error("LLM 调用失败(%s): %s", model_name, exc)
        raise BizError(LLM_NOT_CONFIGURED, f"LLM 调用失败：{exc}")


async def _call_once_async(
    db,
    user_id: int,
    provider: ModelProvider | None,
    messages: list[dict[str, str]],
    scenario: str,
    temperature: float,
    max_tokens: int,
    stream_handler: Callable[[str], None] | None,
) -> str:
    url, model_name, api_key = _endpoint(provider)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload: dict[str, Any] = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    start = time.monotonic()
    prompt_tokens = _count_tokens("".join(m.get("content", "") for m in messages))
    try:
        payload["stream"] = True
        collected: list[str] = []
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                resp.raise_for_status()
                # 慢响应优化：限制「首 token」等待时长，超时立即中断并触发供应商回退，
                # 避免 qwen 等慢模型长时间无输出让用户误以为界面卡死（fallback 事件会推送前端提示）
                stream_iter = resp.aiter_lines()
                got_first_token = False
                while True:
                    try:
                        line = await (
                            asyncio.wait_for(anext(stream_iter), timeout=settings.LLM_FIRST_TOKEN_TIMEOUT_SECONDS)
                            if not got_first_token
                            else anext(stream_iter)
                        )
                    except StopAsyncIteration:
                        break
                    except asyncio.TimeoutError:
                        raise TimeoutError(
                            f"模型 {model_name} 响应过慢：等待首 token 超过 {settings.LLM_FIRST_TOKEN_TIMEOUT_SECONDS}s"
                        )
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                        delta = obj["choices"][0].get("delta", {}).get("content", "")
                    except Exception:
                        delta = ""
                    if delta:
                        got_first_token = True
                        collected.append(delta)
                        if stream_handler:
                            stream_handler(delta)
        content = "".join(collected)

        latency = int((time.monotonic() - start) * 1000)
        completion_tokens = _count_tokens(content)
        _log_call(db, user_id, scenario, model_name, prompt_tokens, completion_tokens, latency, True)
        return content
    except Exception as exc:
        latency = int((time.monotonic() - start) * 1000)
        _log_call(db, user_id, scenario, model_name, prompt_tokens, 0, latency, False, str(exc))
        logger.error("LLM 调用失败(%s): %s", model_name, exc)
        raise BizError(LLM_NOT_CONFIGURED, f"LLM 调用失败：{exc}")


# ---------------------------------------------------------------------------
# 对外入口（带失败回退）
# ---------------------------------------------------------------------------


def chat_completion(
    db,
    user_id: int,
    messages: list[dict[str, str]],
    scenario: str = "chat",
    temperature: float = 0.7,
    max_tokens: int = 2000,
    stream_handler: Callable[[str], None] | None = None,
    provider_id: int | None = None,
    fallback_events: list[dict[str, str]] | None = None,
) -> str:
    """调用 LLM，按供应商路由，失败自动回退默认；全部失败抛 BizError。

    provider_id 为 None 时按「默认供应商 -> 环境变量」回退链路由。
    fallback_events 非空时记录每次回退（供调用方提示用户）。
    """
    candidates = _resolve_candidates(db, provider_id)
    if not candidates:
        fallback = _fallback_answer(messages, scenario)
        if stream_handler:
            for i in range(0, len(fallback), 16):
                stream_handler(fallback[i : i + 16])
        return fallback

    last_err: BizError | None = None
    for idx, provider in enumerate(candidates):
        try:
            return _call_once(db, user_id, provider, messages, scenario, temperature, max_tokens, stream_handler)
        except BizError as exc:
            last_err = exc
            if idx < len(candidates) - 1:
                from_name = provider.name if provider else settings.LLM_MODEL
                to_name = _candidate_name(candidates[idx + 1])
                if fallback_events is not None:
                    fallback_events.append(
                        {"from": from_name, "to": to_name, "message": f"{from_name} 调用失败，已自动回退默认模型 {to_name}"}
                    )
                logger.warning("供应商 %s 调用失败，回退到 %s: %s", from_name, to_name, exc)
    assert last_err is not None
    raise last_err


async def chat_completion_async(
    db,
    user_id: int,
    messages: list[dict[str, str]],
    scenario: str = "chat",
    temperature: float = 0.7,
    max_tokens: int = 2000,
    stream_handler: Callable[[str], None] | None = None,
    provider_id: int | None = None,
    fallback_handler: Callable[[str], None] | None = None,
) -> str:
    """异步流式调用 LLM（与 chat_completion 同逻辑，用于 SSE 场景避免跨线程 DB 访问）。"""
    candidates = _resolve_candidates(db, provider_id)
    if not candidates:
        fallback = _fallback_answer(messages, scenario)
        if stream_handler:
            # 本地演示模式也模拟真实流式节奏，避免前端整段蹦出
            for i in range(0, len(fallback), 12):
                stream_handler(fallback[i : i + 12])
                await asyncio.sleep(0.05)
        return fallback

    last_err: BizError | None = None
    for idx, provider in enumerate(candidates):
        try:
            return await _call_once_async(db, user_id, provider, messages, scenario, temperature, max_tokens, stream_handler)
        except BizError as exc:
            last_err = exc
            if idx < len(candidates) - 1:
                from_name = provider.name if provider else settings.LLM_MODEL
                to_name = _candidate_name(candidates[idx + 1])
                if fallback_handler is not None:
                    fallback_handler(f"{from_name} 调用失败，已自动回退默认模型 {to_name}")
                logger.warning("供应商 %s 调用失败，回退到 %s: %s", from_name, to_name, exc)
    assert last_err is not None
    raise last_err


def _candidate_name(provider: ModelProvider | None) -> str:
    if provider is None:
        return settings.LLM_MODEL
    return provider.name


def _fallback_answer(messages: list[dict[str, str]], scenario: str) -> str:
    """未配置任何 LLM 时的本地模板回答，保证服务可直接运行。"""
    last_user = ""
    for m in reversed(messages):
        if m["role"] == "user":
            last_user = m["content"]
            break
    # 从上下文中尝试抽取用户提供的检索片段
    context = ""
    for m in messages:
        if m["role"] == "system":
            context = m["content"]
            break
    excerpts = [line.strip() for line in context.splitlines() if line.strip()]
    quote = excerpts[-1][:80] if excerpts else ""
    return (
        f"（本地演示模式：未配置任何模型供应商，以下为基于检索片段的占位回答）\n\n"
        f"针对您的问题「{last_user[:100]}」，系统已从知识库检索到相关片段{quote}。\n"
        f"请在系统设置中配置 DEEPSEEK_API_KEY 或新增模型供应商后，即可获得完整的大模型生成回答。"
    )
