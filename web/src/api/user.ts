/**
 * 个人中心接口：资料查询 / 资料更新 / 修改密码 / 部门列表
 */
import { request } from './request'
import type { DeptInfo, UserProfile } from '@/types'

/** 个人中心：完整资料 */
export function getProfile() {
  return request<UserProfile>({
    url: '/user/profile',
    method: 'get',
  })
}

/** 个人中心：更新昵称 / 部门 */
export function updateProfile(payload: { username?: string; dept_id?: number }) {
  return request<UserProfile>({
    url: '/user/profile',
    method: 'put',
    data: payload,
  })
}

/** 个人中心：修改密码（无密码老用户首次设置可不传原密码） */
export function changePassword(payload: { old_password?: string; new_password: string }) {
  return request<void>({
    url: '/user/password',
    method: 'put',
    data: payload,
  })
}

/** 部门列表 */
export function listDepartments() {
  return request<DeptInfo[]>({
    url: '/departments',
    method: 'get',
  })
}
