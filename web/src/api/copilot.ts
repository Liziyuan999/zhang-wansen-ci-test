/**
 * AI 文档 Copilot 接口（功能三）
 */
import { request } from './request'

export interface CopilotCitation {
  chunk_id: string
  doc_id?: number
  doc_name?: string
  page_no?: number | null
  sheet_name?: string | null
  snippet?: string
}

export interface CopilotResult {
  action: 'ask' | 'summary' | 'translate' | 'outline'
  action_label: string
  answer: string
  citations: CopilotCitation[]
  source_text: string
  question: string
  doc_id: number
  doc_name: string
}

export function runCopilot(data: {
  doc_id: number
  action: string
  source_text?: string
  question?: string
}) {
  return request<CopilotResult>({
    url: '/document/copilot',
    method: 'post',
    data,
  })
}
