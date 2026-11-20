/**
 * 会话接口：创建 / 列表 / 详情 / 删除
 * 重置上下文走 chat 接口 PUT /api/chat/conversations/{id}/reset-context（见 chat.ts resetConversationContext）。
 */
import { request } from './request'
import type { ConvDetail, ConvItem } from '@/types'

export function createConversation() {
  return request<ConvItem>({
    url: '/chat/conversations',
    method: 'post',
  })
}

export function listConversations() {
  return request<ConvItem[]>({
    url: '/chat/conversations',
    method: 'get',
  })
}

export function getConversationDetail(convId: number) {
  return request<ConvDetail>({
    url: `/chat/conversations/${convId}`,
    method: 'get',
  })
}

export function deleteConversation(convId: number) {
  return request<void>({
    url: `/chat/conversations/${convId}`,
    method: 'delete',
  })
}
