/**
 * 通知中心接口：分类（团队动态/审批消息/系统消息）+ 未读/已读 + 分页 + 实时推送
 */
import { request } from './request'
import { getAccessToken } from '@/utils/auth-token'
import type { NoticeItem, NoticeListResult, UnreadCount } from '@/types'

/** 发送团队通知（仅 owner/admin） */
export function sendNotice(payload: { team_id: number; title: string; content: string }) {
  return request<NoticeItem>({
    url: '/notice/send',
    method: 'post',
    data: payload,
  })
}

/** 我的通知列表（分类过滤 + 分页，按时间倒序） */
export function listNotices(params: { category?: string; page?: number; page_size?: number } = {}) {
  return request<NoticeListResult>({
    url: '/notice/list',
    method: 'get',
    params: {
      category: params.category || '',
      page: params.page ?? 1,
      page_size: params.page_size ?? 20,
    },
  })
}

/** 未读通知数（总数 + 分类未读数） */
export function getUnreadCount() {
  return request<UnreadCount>({
    url: '/notice/unread-count',
    method: 'get',
  })
}

/** 标记单条通知已读（幂等） */
export function markNoticeRead(notificationId: number) {
  return request<{ id: number; read: boolean }>({
    url: `/notice/${notificationId}/read`,
    method: 'post',
  })
}

/** 一键全部已读 */
export function markAllRead() {
  return request<null>({
    url: '/notice/read-all',
    method: 'post',
  })
}

/** 通知实时推送（SSE）：未读数变化时下发事件，返回可取消的关闭函数 */
export function openNoticeSSE(
  onEvent: (evt: { unread: number; latest_id: number | null; latest_title: string | null; latest_category: string | null }) => void,
): () => void {
  // 修复 P1-2：原实现取 localStorage 的 'access_token'，实际写入键为 'knowseek_access_token'，
  // 取到空串后 SSE 请求必然 401（实时通知完全失效）。统一走 getAccessToken()。
  const token = getAccessToken()
  const controller = new AbortController()
  let closed = false
  let buffer = ''

  async function run() {
    try {
      const resp = await fetch('/api/notice/events?token=' + encodeURIComponent(token), {
        headers: { Accept: 'text/event-stream' },
        signal: controller.signal,
      })
      if (!resp.ok || !resp.body) return
      const reader = resp.body.getReader()
      const decoder = new TextDecoder('utf-8')
      for (;;) {
        const { done, value } = await reader.read()
        if (done || closed) break
        buffer += decoder.decode(value, { stream: true })
        let idx: number
        while ((idx = buffer.indexOf('\n\n')) >= 0) {
          const raw = buffer.slice(0, idx)
          buffer = buffer.slice(idx + 2)
          for (const line of raw.split('\n')) {
            if (!line.startsWith('data: ')) continue
            try {
              const payload = JSON.parse(line.slice(6))
              if (payload.type === 'notice') onEvent(payload)
            } catch {
              // 忽略非法数据帧
            }
          }
        }
      }
    } catch {
      // 连接中断，由外部轮询兜底
    }
  }
  run()

  return () => {
    closed = true
    controller.abort()
  }
}
