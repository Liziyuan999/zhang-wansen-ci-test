/**
 * 管理后台接口：用户 / 部门 / 文档 / 会话 / 反馈 / 日志 / LLM 记录 / 配置
 */
import { request } from './request'
import type {
  AdminConversation,
  AdminDept,
  AdminDoc,
  AdminFeedback,
  AdminUser,
  LlmLogItem,
  ModelProviderItem,
  OperationLogItem,
  PageResult,
  SysConfigItem,
} from '@/types'

/** 用户列表 */
export function listUsers(params: { page?: number; page_size?: number; keyword?: string }) {
  return request<PageResult<AdminUser>>({
    url: '/admin/users',
    method: 'get',
    params,
  })
}

/** 更新用户（角色/状态/部门/名称） */
export function updateUser(
  userId: number,
  payload: { role?: string; status?: string; dept_id?: number; username?: string },
) {
  return request<void>({
    url: `/admin/users/${userId}`,
    method: 'patch',
    data: payload,
  })
}

/** 部门列表（管理，树形） */
export function listAdminDepartments() {
  return request<AdminDept[]>({
    url: '/admin/departments',
    method: 'get',
  })
}

/** 新增部门 */
export function createAdminDepartment(payload: {
  dept_name: string
  parent_id?: number | null
  leader_id?: number | null
  description?: string
  sort_order?: number
}) {
  return request<{ id: number; dept_name: string }>({
    url: '/admin/departments',
    method: 'post',
    data: payload,
  })
}

/** 编辑部门 */
export function updateAdminDepartment(
  deptId: number,
  payload: {
    dept_name?: string
    parent_id?: number | null
    leader_id?: number | null
    description?: string | null
    sort_order?: number
  },
) {
  return request<void>({
    url: `/admin/departments/${deptId}`,
    method: 'put',
    data: payload,
  })
}

/** 删除部门 */
export function deleteAdminDepartment(deptId: number) {
  return request<void>({
    url: `/admin/departments/${deptId}`,
    method: 'delete',
  })
}

/** 操作日志 */
export function listOperationLogs(params: { page?: number; page_size?: number; action?: string }) {
  return request<PageResult<OperationLogItem>>({
    url: '/admin/logs',
    method: 'get',
    params,
  })
}

/** LLM 调用记录 */
export function listLlmLogs(params: { page?: number; page_size?: number }) {
  return request<PageResult<LlmLogItem>>({
    url: '/admin/llm-logs',
    method: 'get',
    params,
  })
}

/** 系统配置列表 */
export function listSysConfigs() {
  return request<SysConfigItem[]>({
    url: '/admin/configs',
    method: 'get',
  })
}

/** 更新系统配置 */
export function updateSysConfig(config_key: string, config_value: string, description?: string) {
  return request<void>({
    url: `/admin/configs/${config_key}`,
    method: 'put',
    data: { config_key, config_value, description },
  })
}

/** 文档总览（管理） */
export function listAdminDocuments(params: { page?: number; page_size?: number; keyword?: string; file_type?: string; status?: string }) {
  return request<PageResult<AdminDoc>>({
    url: '/admin/documents',
    method: 'get',
    params,
  })
}

/** 会话总览（管理） */
export function listAdminConversations(params: { page?: number; page_size?: number; keyword?: string }) {
  return request<PageResult<AdminConversation>>({
    url: '/admin/conversations',
    method: 'get',
    params,
  })
}

/** 用户反馈列表（管理） */
export function listAdminFeedback(params: { page?: number; page_size?: number; status?: string }) {
  return request<PageResult<AdminFeedback>>({
    url: '/admin/feedback',
    method: 'get',
    params,
  })
}

/** 处理用户反馈 */
export function handleFeedback(feedbackId: number) {
  return request<void>({
    url: `/admin/feedback/${feedbackId}/handle`,
    method: 'post',
  })
}

/** 模型供应商列表 */
export function listModelProviders() {
  return request<ModelProviderItem[]>({
    url: '/admin/model-providers',
    method: 'get',
  })
}

/** 新增模型供应商 */
export function createModelProvider(payload: { name: string; base_url: string; model: string; api_key: string; is_default?: boolean; enabled?: boolean }) {
  return request<ModelProviderItem>({
    url: '/admin/model-providers',
    method: 'post',
    data: payload,
  })
}

/** 更新模型供应商（api_key 留空不覆盖） */
export function updateModelProvider(providerId: number, payload: { name?: string; base_url?: string; model?: string; api_key?: string; is_default?: boolean; enabled?: boolean }) {
  return request<ModelProviderItem>({
    url: `/admin/model-providers/${providerId}`,
    method: 'put',
    data: payload,
  })
}

/** 删除模型供应商 */
export function deleteModelProvider(providerId: number) {
  return request<void>({
    url: `/admin/model-providers/${providerId}`,
    method: 'delete',
  })
}

/** 设为默认供应商 */
export function setDefaultModelProvider(providerId: number) {
  return request<ModelProviderItem>({
    url: `/admin/model-providers/${providerId}/set-default`,
    method: 'post',
  })
}

/** 角色权限条目（团队维度） */
export interface AdminRoleItem {
  team_id: number
  team_name: string
  role_key: string
  role_name: string
  built_in: boolean
  editable: boolean
  perms: string[]
  perm_count: number
  member_count: number
  remark: string
}

/** 权限点定义 */
export interface AdminPermPoint {
  key: string
  name: string
  desc?: string
}

/** 角色权限总览结果 */
export interface AdminRoleOverview {
  catalog: AdminPermPoint[]
  items: AdminRoleItem[]
  total: number
  team_total: number
  custom_total: number
  perm_total: number
}

/** 全平台角色权限总览 */
export function roleOverview(params: { keyword?: string; only_custom?: boolean } = {}) {
  return request<AdminRoleOverview>({
    url: '/admin/role-overview',
    method: 'get',
    params,
  })
}
