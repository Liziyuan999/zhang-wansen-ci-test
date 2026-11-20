/**
 * 认证接口：验证码发送 / 注册 / 登录 / 刷新 / 找回密码 / SSO 预留 / 当前用户 / 部门列表
 * 说明：后端登录为「QQ 邮箱 + 验证码」方式（POST /api/auth/login），注册亦走验证码。
 */
// ===== 逐行注释：认证接口封装（JWT 双 token 相关） =====
// 1. sendCode：四种用途（register 注册 / login 登录 / reset 找回密码 / unlock 解锁），
//    后端校验频率限制后发邮件；前端在登录/注册/忘记密码/锁定页分别调用。
// 2. loginApi：核心登录接口，mode 二选一——"password"（邮箱+密码）或 "code"（邮箱+验证码）；
//    remember 为"记住我"（延长 access token 有效期）。返回 TokenData（双 token + user）。
// 3. refreshApi：由 request.ts 的 401 拦截器在 access 过期时自动调用，传入旧 refresh_token
//    换取新的双 token（后端同时轮换旧 refresh token），成功后重放原请求。
// 4. logoutApi：主动退出时调用，撤销服务端 refresh token（本地清理由 userStore.logout 完成）。
// 5. lockStatus / unlockApi：登录锁定查询与邮箱验证码自助解锁（连续失败锁定后的恢复通道）。
// 6. registerApi 注册即登录（自动签发 token）；getMe 拉取当前用户；listDepartments 供注册下拉选部门。
import { request } from './request'
import type { ApiResponse, DeptInfo, TokenData, UserInfo } from '@/types'

/** 发送验证码（purpose: register | login | reset | unlock） */
export function sendCode(email: string, purpose: 'register' | 'login' | 'reset' | 'unlock') {
  return request<void>({
    url: '/auth/send-code',
    method: 'post',
    data: { email, purpose },
  })
}

/** 查询账号锁定状态（返回 locked / retry_after_seconds / lock_minutes） */
export function lockStatus(email: string) {
  return request<{ locked: boolean; fail_count: number; retry_after_seconds: number; lock_minutes: number }>({
    url: '/auth/lock-status',
    method: 'post',
    data: { email },
  })
}

/** 邮箱验证码解锁（连续失败锁定后的自助解锁途径） */
export function unlockApi(email: string, code: string) {
  return request<void>({
    url: '/auth/unlock',
    method: 'post',
    data: { email, code },
  })
}

/** 注册（自动登录，返回 token） */
export function registerApi(payload: {
  email: string
  code: string
  username: string
  password: string
  dept_name: string
}) {
  return request<TokenData>({
    url: '/auth/register',
    method: 'post',
    data: payload,
  })
}

/** 登录（双模式：mode=code 邮箱+验证码；mode=password 邮箱+密码，支持记住我） */
export function loginApi(payload: {
  email: string
  mode?: 'code' | 'password'
  code?: string
  password?: string
  remember?: boolean
}) {
  return request<TokenData>({
    url: '/auth/login',
    method: 'post',
    data: payload,
  })
}

/** 刷新 token（供 request.ts 401 重试使用） */
export function refreshApi(refresh_token: string) {
  return request<TokenData>({
    url: '/auth/refresh',
    method: 'post',
    data: { refresh_token },
  })
}

/** 退出登录：撤销服务端 refresh token（本地清理由 userStore.logout 完成） */
export function logoutApi(refresh_token: string) {
  return request<void>({
    url: '/auth/logout',
    method: 'post',
    data: { refresh_token },
  })
}

/** 找回密码：发送 reset 用途验证码 */
export function forgotPassword(email: string) {
  return request<void>({
    url: '/auth/forgot-password',
    method: 'post',
    data: { email },
  })
}

/** 重置密码：校验验证码并设置新密码 */
export function resetPassword(payload: { email: string; code: string; new_password: string }) {
  return request<void>({
    url: '/auth/reset-password',
    method: 'post',
    data: payload,
  })
}

/** 企业 SSO/OAuth 入口预留（钉钉/企业微信/LDAP 配置位） */
export function getSsoConfig() {
  return request<Array<{ provider: string; name: string; enabled: boolean; configured: boolean; hint: string }>>({
    url: '/auth/sso-config',
    method: 'get',
  })
}

/** 当前用户信息 */
export function getMe() {
  return request<UserInfo>({
    url: '/auth/me',
    method: 'get',
  })
}

/** 部门列表（注册时下拉选择，后端为全量开放接口） */
export function listDepartments() {
  return request<DeptInfo[]>({
    url: '/departments',
    method: 'get',
  })
}

export type { ApiResponse }
