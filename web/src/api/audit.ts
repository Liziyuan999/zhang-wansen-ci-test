/**
 * 审计日志接口
 */
import { request } from './request'
import type { PageResult } from '@/types'

/** 审计日志条目 */
export interface AuditLogItem {
  id: number
  user_id: number | null
  username: string
  email: string | null
  module: string
  module_label: string
  action: string
  action_label: string
  method?: string
  path?: string
  duration_ms?: number | null
  detail: string | null
  ip: string | null
  status: string
  create_time: string
}

/** 审计分类 */
export interface AuditModuleOption {
  module: string
  module_label: string
  actions: string[]
}

/** 审计日志查询参数 */
export interface AuditLogQuery {
  page?: number
  page_size?: number
  module?: string
  action?: string
  operator?: string
  start?: string
  end?: string
  status?: string
}

/** 审计分类枚举 */
export function listAuditModules() {
  return request<AuditModuleOption[]>({
    url: '/audit/modules',
    method: 'get',
  })
}

/** 审计日志分页查询 */
export function listAuditLogs(params: AuditLogQuery) {
  return request<PageResult<AuditLogItem>>({
    url: '/audit/logs',
    method: 'get',
    params,
  })
}
