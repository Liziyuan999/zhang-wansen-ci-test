# -*- coding: utf-8 -*-
"""全网知识库：联网搜索服务（开发环境免密钥方案，生产可替换商业端点）。

当前实现（多源聚合）：
  1. Bing 网页搜索结果页抓取解析（无需 API Key，8 秒超时）
  2. Wikipedia 开放 API（zh.wikipedia.org，action=query&list=search&format=json）
两源结果按标题/URL 去重合并，总条数不超过 max_results；任一源异常独立兜底，
不影响另一源，保证主流程（RAG 对话 / Agent 任务）不受网络影响。
合并采用源间轮询（round-robin）：轮流从各源取结果并去重，避免单一源提前填满
max_results 导致另一源结果无法进入最终列表。

生产替换建议：可替换为 Bing Web Search API / SerpAPI / 智谱 web_search 等
商业端点，只需保持 search_web(query, max_results) 返回 [{title, url, snippet}]
的签名即可，上层无需改动。
"""
import base64
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from html import unescape
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests

logger = logging.getLogger(__name__)

SEARCH_ENDPOINT = "https://cn.bing.com/search"
WIKIPEDIA_API_ENDPOINT = "https://zh.wikipedia.org/w/api.php"
TIMEOUT_SECONDS = 8
DEFAULT_MAX_RESULTS = 5
# 单源预取上限：两源各自取回后合并截断到 max_results，保证最终条数准确
_MAX_PER_SOURCE = 10

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def _clean(text: str) -> str:
    """去掉 HTML 标签并把实体还原为纯文本。"""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _normalize_url(url: str) -> str:
    """还原 Bing /ck/a 跳转链接中的真实目标 URL（u= 参数为 base64）。"""
    if "/ck/a" not in url:
        return url
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    u = params.get("u")
    if not u:
        return url
    try:
        raw = u[0]
        padded = raw + "=" * (-len(raw) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8", "ignore")
        if decoded.startswith(("http://", "https://")):
            return decoded
    except Exception:  # noqa: BLE001
        pass
    return url


def search_web(query: str, max_results: int = DEFAULT_MAX_RESULTS) -> list[dict[str, Any]]:
    """联网搜索（多源聚合，多源并行），返回 [{title, url, snippet}]；失败/超时返回空列表。"""
    if not query or not query.strip():
        return []
    # 性能优化：原实现两个源串行抓取，网络受限时单源超时 8s 会累计到 16~18s（实测 17.5s 首帧）；
    # 改为线程池并行后整体耗时≈单源最长耗时，且各源仍独立兜底（一个源异常不影响另一个源）。
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="websearch") as pool:
        futures = [
            pool.submit(_search_bing, query, _MAX_PER_SOURCE),
            pool.submit(_search_wikipedia, query, _MAX_PER_SOURCE),
        ]
        source_results: list[list[dict[str, Any]]] = []
        for fut in futures:
            try:
                source_results.append(fut.result())
            except Exception as exc:  # noqa: BLE001
                logger.warning("检索源异常（独立兜底，忽略该源）: %s", exc)
                source_results.append([])
    return _merge_results(source_results, max_results)


def _search_bing(query: str, max_results: int) -> list[dict[str, Any]]:
    """Bing 源：搜索结果页 HTML 抓取解析；异常独立兜底返回空列表。"""
    try:
        resp = requests.get(
            SEARCH_ENDPOINT,
            params={"q": query.strip(), "setlang": "zh-hans"},
            headers={
                "User-Agent": _UA,
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
            timeout=TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return _parse_bing(resp.text, max_results)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Bing 检索失败（独立兜底，忽略该源）: %s", exc)
        return []


def _search_wikipedia(query: str, max_results: int) -> list[dict[str, Any]]:
    """Wikipedia 源：zh.wikipedia.org 开放 API 检索；异常独立兜底返回空列表。"""
    try:
        resp = requests.get(
            WIKIPEDIA_API_ENDPOINT,
            params={
                "action": "query",
                "list": "search",
                "format": "json",
                "srsearch": query.strip(),
                "srlimit": max_results,
                "utf8": 1,
            },
            headers={"User-Agent": _UA},
            timeout=TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = resp.json()
        results: list[dict[str, Any]] = []
        for item in data.get("query", {}).get("search", []) or []:
            title = (item.get("title") or "").strip()
            if not title:
                continue
            page_url = "https://zh.wikipedia.org/wiki/" + requests.utils.quote(title.replace(" ", "_"))
            snippet = _clean(item.get("snippet", "") or "")
            results.append({"title": title, "url": page_url, "snippet": snippet})
        return results[:max_results]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Wikipedia 检索失败（独立兜底，忽略该源）: %s", exc)
        return []


def _merge_results(source_results: list[list[dict[str, Any]]], max_results: int) -> list[dict[str, Any]]:
    """按 URL / 标题去重合并多源结果，总条数不超过 max_results。

    源间轮询：每轮依次从各源取 1 条（跳过已见 URL/标题），保证多源结果
    都有机会进入最终列表，而不是被结果数更多的源提前填满。
    """
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    merged: list[dict[str, Any]] = []
    pool = [list(results) for results in source_results if results]

    while len(merged) < max_results:
        progressed = False
        for src in pool:
            if len(merged) >= max_results:
                break
            while src:
                r = src.pop(0)
                url = (r.get("url") or "").strip().lower()
                title = (r.get("title") or "").strip().lower()
                if (url and url in seen_urls) or (title and title in seen_titles):
                    continue
                if url:
                    seen_urls.add(url)
                if title:
                    seen_titles.add(title)
                merged.append(r)
                progressed = True
                break
        if not progressed:
            break
    return merged[:max_results]


def _parse_bing(html_text: str, max_results: int) -> list[dict[str, Any]]:
    """解析 Bing 结果页：<li class="b_algo"> 块内 <h2><a href>标题</a></h2> 与 <p>摘要</p>。"""
    results: list[dict[str, Any]] = []
    block_re = re.compile(r'<li[^>]*class="b_algo"[^>]*>.*?</li>', re.S)
    title_re = re.compile(r'<h2[^>]*><a[^>]*href="([^"]+)"[^>]*>(.*?)</a></h2>', re.S)
    snippet_re = re.compile(r'<p[^>]*>(.*?)</p>', re.S)

    for block in block_re.findall(html_text):
        if len(results) >= max_results:
            break
        m = title_re.search(block)
        if not m:
            continue
        url = _normalize_url(m.group(1).strip())
        title = _clean(m.group(2))
        sn = snippet_re.search(block)
        snippet = _clean(sn.group(1)) if sn else ""
        if not title or not url:
            continue
        results.append({"title": title, "url": url, "snippet": snippet})
    return results
