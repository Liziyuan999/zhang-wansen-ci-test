/**
 * AI 周报接口
 */
import { request } from './request'

/** 周报模板章节 */
export interface ReportSection {
  title: string
  desc: string
}

/** 周报模板 */
export interface ReportTemplate {
  title: string
  summary: string
  sections: ReportSection[]
}

/** 生成的周报 */
export interface WeeklyReport {
  markdown: string
  html: string
  period_label: string
  generated_at: string
  source: 'llm' | 'template'
}

/** 获取周报模板骨架 */
export function getReportTemplate() {
  return request<ReportTemplate>({
    url: '/report/template',
    method: 'get',
  })
}

/** 生成周报草稿 */
export function generateWeeklyReport(payload: { period: string; start_date?: string; end_date?: string; focus?: string; model_provider_id?: number | null }) {
  return request<WeeklyReport>({
    url: '/report/weekly',
    method: 'post',
    data: { ...payload, model_provider_id: payload.model_provider_id ?? null },
  })
}
