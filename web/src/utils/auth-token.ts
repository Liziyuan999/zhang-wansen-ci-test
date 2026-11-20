/**
 * 登录态 token 统一读取工具（修复 P1-2 / P1-2 附带问题）。
 *
 * 背景：登录成功后 token 由 stores/user.ts 写入 localStorage，键名为
 * `knowseek_access_token`；但 notice.ts（SSE 实时通知）与 team.ts（共享文档下载）
 * 曾直接读 `access_token`，取不到空串后请求变成 `Bearer ` / `token=` 空值，
 * 导致 401（通知 SSE 完全不可用、共享文档下载失败）。
 *
 * 约定：所有非 axios 的裸 fetch（SSE / 下载）一律通过本模块读取 token，禁止各处硬编码键名。
 */

export const ACCESS_TOKEN_KEY = 'knowseek_access_token'
export const REFRESH_TOKEN_KEY = 'knowseek_refresh_token'
export const USER_INFO_KEY = 'knowseek_user_info'

/** 读取当前登录用户的 access token；未登录或读取失败返回空串。 */
export function getAccessToken(): string {
  try {
    return localStorage.getItem(ACCESS_TOKEN_KEY) || ''
  } catch {
    return ''
  }
}

/** 读取当前登录用户的 refresh token；未登录或读取失败返回空串。 */
export function getRefreshToken(): string {
  try {
    return localStorage.getItem(REFRESH_TOKEN_KEY) || ''
  } catch {
    return ''
  }
}
