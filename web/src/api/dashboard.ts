/**
 * 数据看板接口
 */
import { request } from './request'

/** 看板聚合数据（后端 /api/dashboard/summary） */
export interface DashboardSummary {
  document: { total: number; today: number; this_week: number; pending: number; processing: number; ready: number; failed: number }
  retrieval: { count: number; success_rate: number }
  conversation: { count: number; messages: number }
  agent: { total: number; done: number; running: number; finished: number; failed: number; by_type?: { name: string; value: number }[] }
  organization: { users: number; teams: number; departments: number }
  trend_7d: {
    documents: number[]
    retrievals: number[]
    conversations: number[]
    agents: number[]
    dates: string[]
  }
}

/** 数据看板-聚合统计 */
export function getDashboardSummary() {
  return request<DashboardSummary>({
    url: '/dashboard/summary',
    method: 'get',
  })
}

/* ---------------- 智能看板升级（功能四） ---------------- */

/** 知识热度榜 */
export interface KnowledgeHotItem {
  rank: number
  doc_id: number
  doc_name: string
  file_type: string
  view_count: number
  retrieve_count: number
  heat_score: number
  update_time: string | null
}

export function getKnowledgeHot() {
  return request<{ list: KnowledgeHotItem[]; total: number }>({
    url: '/dashboard/knowledge-hot',
    method: 'get',
  })
}

/** 部门活跃度 */
export interface DeptActivityItem {
  dept_id: number
  dept_name: string
  documents: number
  conversations: number
  retrievals: number
  total: number
}

export function getDeptActivity() {
  return request<{ list: DeptActivityItem[]; days: number }>({
    url: '/dashboard/dept-activity',
    method: 'get',
  })
}

/** 检索热力图 */
export interface RetrievalHeatItem {
  date: string
  count: number
}

export function getRetrievalHeatmap() {
  return request<{ list: RetrievalHeatItem[]; max: number; days: number }>({
    url: '/dashboard/retrieval-heatmap',
    method: 'get',
  })
}

/** AI 用量报表 */
export interface LlmUsageTrend {
  date: string
  calls: number
  success_rate: number
  avg_latency_ms: number
}

export interface LlmModelUsage {
  model_name: string
  calls: number
  success_rate: number
  avg_latency_ms: number
}

export function getLlmUsage() {
  return request<{
    days: number
    trend: LlmUsageTrend[]
    summary: {
      total_calls: number
      success_rate: number
      avg_latency_ms: number
      by_model: LlmModelUsage[]
    }
  }>({
    url: '/dashboard/llm-usage',
    method: 'get',
  })
}
