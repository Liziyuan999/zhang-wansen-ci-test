/**
 * Axios 实例：baseURL /api、token 注入、统一 code 处理、401 刷新重试一次
 */
import axios, { AxiosError, type AxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import type { ApiResponse, TokenData } from '@/types'

const instance = axios.create({
  baseURL: '/api',
  timeout: 60_000,
})

/** 是否正在刷新 token（避免并发重复刷新） */
let isRefreshing = false
/** 等待刷新完成后重放请求的队列 */
let pendingQueue: Array<(token: string | null) => void> = []

/** 401 刷新成功后的重放逻辑 */
function flushQueue(token: string | null) {
  pendingQueue.forEach((cb) => cb(token))
  pendingQueue = []
}

/** 登录态失效：静默清理本地登录态并跳转登录页（不弹任何错误提示） */
async function handleAuthFailure() {
  const userStore = useUserStore()
  userStore.logout()
  const { default: router } = await import('@/router')
  if (router.currentRoute.value.path !== '/login') {
    router.push({ path: '/login', query: { redirect: router.currentRoute.value.fullPath } })
  }
}

instance.interceptors.request.use((config) => {
  const userStore = useUserStore()
  if (userStore.accessToken) {
    config.headers.Authorization = `Bearer ${userStore.accessToken}`
  }
  return config
})

instance.interceptors.response.use(
  (response) => {
    const payload = response.data as ApiResponse
    if (payload && typeof payload === 'object' && 'code' in payload) {
      if (payload.code !== 0) {
        const err = new Error(payload.message || '请求失败') as Error & { code?: number; data?: unknown }
        err.code = payload.code
        err.data = payload.data
        ElMessage.error(payload.message || '请求失败')
        return Promise.reject(err)
      }
      return response
    }
    return response
  },
  async (error: AxiosError<ApiResponse>) => {
    const userStore = useUserStore()
    const status = error.response?.status
    const original = error.config as AxiosRequestConfig & { _retry?: boolean }

    // 401 且带 refresh token，且未重试过 → 刷新后重放一次
    if (status === 401 && !original._retry && userStore.refreshToken) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          pendingQueue.push((token) => {
            if (!token) {
              reject(error)
              return
            }
            original._retry = true
            original.headers = { ...(original.headers || {}), Authorization: `Bearer ${token}` }
            resolve(instance(original))
          })
        })
      }

      original._retry = true
      isRefreshing = true
      try {
        const refreshResp = await axios.post<ApiResponse<TokenData>>('/api/auth/refresh', {
          refresh_token: userStore.refreshToken,
        })
        const tokens = refreshResp.data.data
        if (!tokens) throw new Error('刷新 token 失败')
        userStore.setTokens(tokens)
        flushQueue(tokens.access_token)
        original.headers = { ...(original.headers || {}), Authorization: `Bearer ${tokens.access_token}` }
        return instance(original)
      } catch (refreshError) {
        flushQueue(null)
        await handleAuthFailure()
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    // 登录态失效（401 / token 无效）：静默清理本地登录态并跳转登录页，不弹任何错误提示
    if (status === 401) {
      await handleAuthFailure()
      return Promise.reject(error)
    }

    const message = error.response?.data?.message || error.message || '网络请求失败'
    ElMessage.error(message)
    return Promise.reject(error)
  },
)

/** 泛型请求封装：返回 data 字段 */
export async function request<T = unknown>(config: AxiosRequestConfig): Promise<T> {
  const response = await instance.request<ApiResponse<T>>(config)
  return response.data.data as T
}

export default instance
export { instance }
