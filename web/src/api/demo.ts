/**
 * 演示模式接口（功能五）
 */
import { request } from './request'

export interface DemoStatus {
  active: boolean
  seeded_at: string | null
  counts: {
    departments: number
    users: number
    documents: number
    llm_logs: number
  }
}

export interface DemoSeedResult {
  active: boolean
  seeded_at: string
  departments: number
  users: number
  documents: number
  entities: number
  relations: number
  conversations: number
  keep_original: boolean
}

/** 一键灌入演示数据 */
export function seedDemo(keepOriginal = true) {
  return request<DemoSeedResult>({
    url: '/demo/seed',
    method: 'post',
    data: { keep_original: keepOriginal },
  })
}

/** 查询演示状态 */
export function getDemoStatus() {
  return request<DemoStatus>({
    url: '/demo/status',
    method: 'get',
  })
}

/** 一键清除演示数据（仅演示标记数据） */
export function clearDemo() {
  return request<{ cleared: boolean; removed_documents: number; removed_users: number }>({
    url: '/demo/clear',
    method: 'post',
  })
}
