/**
 * 用户状态：token / userInfo / dept 持久化（localStorage）
 */
// ===== 逐行注释：用户全局状态（Pinia store） =====
// 1. 持久化：access/refresh token 与用户信息写入 localStorage（三个固定 key），
//    刷新页面后 isLoggedIn 仍为 true；readUser 对损坏 JSON 做容错（返回 null）。
// 2. getters：isLoggedIn（有 accessToken 且有用户信息才算登录）、
//    isAdmin（role == 'admin'，供路由 requiresAdmin 守卫）、deptName（当前部门名）。
// 3. setTokens：登录/注册/刷新成功后一次性落库双 token + 用户信息（内存 + localStorage）。
// 4. setUserInfo：个人中心编辑资料后单独更新用户信息，不动 token。
// 5. logout：清空本地三件套并通知服务端撤销 refresh token（logoutApi），
//    失败也静默忽略（.catch(() => {})），保证本地退出始终成功。
// ===== 逐行注释：双 token 存储要点 =====
// - accessToken：短效（分钟级），每次 API 请求携带，401 时自动刷新替换。
// - refreshToken：长效（天级），仅 refreshApi 使用；logout 时优先取其值发服务端撤销。
import { defineStore } from 'pinia'
import { logoutApi } from '@/api/auth'
import { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY, USER_INFO_KEY } from '@/utils/auth-token'
import type { TokenData, UserInfo } from '@/types'

// 键名统一由 utils/auth-token.ts 定义，避免各处硬编码不一致（P1-2 根治）
const ACCESS_KEY = ACCESS_TOKEN_KEY
const REFRESH_KEY = REFRESH_TOKEN_KEY
const USER_KEY = USER_INFO_KEY

function readUser(): UserInfo | null {
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? (JSON.parse(raw) as UserInfo) : null
  } catch {
    return null
  }
}

export const useUserStore = defineStore('user', {
  state: () => ({
    accessToken: localStorage.getItem(ACCESS_KEY) || '',
    refreshToken: localStorage.getItem(REFRESH_KEY) || '',
    userInfo: readUser() as UserInfo | null,
  }),
  getters: {
    isLoggedIn: (state) => !!state.accessToken && !!state.userInfo,
    isAdmin: (state) => state.userInfo?.role === 'admin',
    deptName: (state) => state.userInfo?.dept_name || '',
  },
  actions: {
    setTokens(tokens: TokenData) {
      this.accessToken = tokens.access_token
      this.refreshToken = tokens.refresh_token
      this.userInfo = tokens.user
      localStorage.setItem(ACCESS_KEY, tokens.access_token)
      localStorage.setItem(REFRESH_KEY, tokens.refresh_token)
      localStorage.setItem(USER_KEY, JSON.stringify(tokens.user))
    },
    setUserInfo(user: UserInfo) {
      this.userInfo = user
      localStorage.setItem(USER_KEY, JSON.stringify(user))
    },
    logout() {
      const rt = this.refreshToken
      this.accessToken = ''
      this.refreshToken = ''
      this.userInfo = null
      localStorage.removeItem(ACCESS_KEY)
      localStorage.removeItem(REFRESH_KEY)
      localStorage.removeItem(USER_KEY)
      // 通知服务端撤销 refresh token（失败不影响本地退出）
      if (rt) {
        logoutApi(rt).catch(() => {})
      }
    },
  },
})
