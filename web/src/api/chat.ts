/**
 * 对话接口：SSE 流式对话（fetch + ReadableStream 解析）+ 反馈
 * 后端 SSE 事件：data: {"type":"citations"|"web_sources"|"delta"|"done"|"error", ...}
 */
// ===== 逐行注释：SSE 流式对话封装 =====
// 1. askSSE：直接使用原生 fetch 而非 axios 实例——流式响应需要在 ReadableStream 上边读边解析，
//    axios 默认会等整个响应体结束才 resolve，无法实现打字机效果。
// 2. 请求头携带 Bearer accessToken；401 时静默清理本地登录态并跳转 /login（不弹错误提示）。
// 3. 慢响应兜底：SLOW_MS（默认 50000ms）内无 delta 增量则触发 onSlowTip 一次，提示用户
//    模型响应较慢而非卡死；每次收到 delta 都会重置定时器（armSlowTimer）。
// 4. SSE 解析：事件以 data: 前缀开头、空行分隔；逐行 parseLine 按 type 分发：
//    citations（引用片段）/ web_sources（联网来源）/ delta（增量文本）/ fallback（模型回退）/
//    done（结束，携带 conv_id/msg_id）/ error（失败）。
// 5. buffer 缓冲处理：split('\n\n') 取出完整事件块，残余部分保留到下一轮循环；
//    流结束后再处理残留 buffer，防止最后一条事件因未遇到空行而丢失。
import { request } from './request'
import type { Citation, ModelProviderOption, SSEEvent, WebSource } from '@/types'
import { useUserStore } from '@/stores/user'

export interface AskSSECallbacks {
  onCitation?: (citations: Citation[]) => void
  onWebSources?: (sources: WebSource[]) => void
  onDelta?: (text: string) => void
  onDone?: (payload: { conv_id: number; msg_id: number }) => void
  onError?: (message: string) => void
  /** 模型供应商回退（后端推送 fallback 事件） */
  onFallback?: (message: string) => void
  /** 首 token 等待过久提示（slowTimeoutMs 控制阈值，默认 50000ms） */
  onSlowTip?: (message: string) => void
  /** 无增量多久后触发 onSlowTip（毫秒） */
  slowTimeoutMs?: number
  signal?: AbortSignal
}

export async function askSSE(
  convId: number | null,
  question: string,
  callbacks: AskSSECallbacks,
  webSearch = false,
  providerId: number | null = null,
  docIds: number[] = [],
): Promise<void> {
  const userStore = useUserStore()
  const response = await fetch('/api/chat/ask', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${userStore.accessToken}`,
    },
    body: JSON.stringify({ conv_id: convId, question, web_search: webSearch, model_provider_id: providerId, doc_ids: docIds.length ? docIds : undefined }),
    signal: callbacks.signal,
  })

  if (!response.ok) {
    // 401 登录态失效：静默清理本地登录态并跳转登录页，不弹任何错误提示
    if (response.status === 401) {
      userStore.logout()
      window.location.href = '/login'
      return
    }
    callbacks.onError?.(`请求失败（HTTP ${response.status}）`)
    return
  }

  if (!response.body) {
    callbacks.onError?.('浏览器不支持流式响应')
    return
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  // 慢响应兜底：长时间无增量时提示用户，避免误以为卡死（只提示一次）
  let slowTipSent = false
  const SLOW_MS = callbacks.slowTimeoutMs ?? 50000
  let slowTimer: ReturnType<typeof setTimeout> | null = null
  const armSlowTimer = () => {
    if (slowTimer) clearTimeout(slowTimer)
    if (!callbacks.onSlowTip || slowTipSent) return
    slowTimer = setTimeout(() => {
      if (!slowTipSent) {
        slowTipSent = true
        callbacks.onSlowTip?.(`模型响应较慢（已等待 ${Math.round(SLOW_MS / 1000)}s），请耐心等待，超时后将自动切换可用模型`)
      }
    }, SLOW_MS)
  }
  const clearSlowTimer = () => {
    if (slowTimer) {
      clearTimeout(slowTimer)
      slowTimer = null
    }
  }

  const parseLine = (line: string) => {
    if (!line.startsWith('data:')) return
    const json = line.slice(5).trim()
    if (!json) return
    let event: SSEEvent
    try {
      event = JSON.parse(json) as SSEEvent
    } catch {
      return
    }
    switch (event.type) {
      case 'citations':
        callbacks.onCitation?.((event.data as unknown as Citation[]) || [])
        break
      case 'web_sources':
        callbacks.onWebSources?.((event.data as unknown as WebSource[]) || [])
        break
      case 'delta':
        callbacks.onDelta?.(event.content || '')
        armSlowTimer()
        break
      case 'fallback':
        callbacks.onFallback?.(event.message || '模型调用失败，已自动回退')
        break
      case 'done':
        clearSlowTimer()
        callbacks.onDone?.({ conv_id: event.conv_id || 0, msg_id: event.msg_id || 0 })
        break
      case 'error':
        clearSlowTimer()
        callbacks.onError?.(event.message || '对话生成失败')
        break
    }
  }

  armSlowTimer()
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    // SSE 事件以空行分隔
    const parts = buffer.split('\n\n')
    buffer = parts.pop() || ''
    parts.forEach((block) => {
      block.split('\n').forEach((line) => parseLine(line))
    })
  }
  clearSlowTimer()
  // 处理残留
  buffer
    .split('\n')
    .filter((l) => l.startsWith('data:'))
    .forEach((line) => parseLine(line))
}

/** 提交消息反馈 */
export function sendFeedback(payload: { msg_id: number; score: 'good' | 'bad'; content?: string }) {
  return request<{ feedback_id: number }>({
    url: '/chat/feedback',
    method: 'post',
    data: payload,
  })
}

/** 重置会话上下文（清空历史消息，后续提问不再携带历史） */
export function resetConversationContext(convId: number) {
  return request<void>({
    url: `/chat/conversations/${convId}/reset-context`,
    method: 'put',
  })
}

export interface LlmStatus {
  configured: boolean
  model: string
  base_url: string
  /** 可选的模型供应商列表（仅已启用且已配置 API Key） */
  providers: ModelProviderOption[]
}

/** 查询 LLM 接入状态（不暴露密钥） */
export function getLlmStatus() {
  return request<LlmStatus>({
    url: '/chat/llm-status',
    method: 'get',
  })
}
