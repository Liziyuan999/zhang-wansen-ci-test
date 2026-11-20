/**
 * Agent 任务接口：创建 / 确认 / 列表 / 详情 / 模板 / 画布运行
 */
// ===== 逐行注释：Agent 任务接口封装 =====
// 1. createAgentTask：创建任务，task_type 三选一（weekly_report 周报 / doc_compare 文档对比 /
//    write_plan 写作方案），doc_ids 素材文档，params 为各类型专属参数，
//    canvas_json 为画布工作流 JSON（canvas 模式专用），model_provider_id 指定模型供应商。
// 2. confirmAgentTask：任务执行完成后的用户确认/驳回（confirm 布尔），
//    确认后任务状态落定并触发下游（如周报推送）；驳回则重新生成。
// 3. 模板系列（list/create/update/delete/run）：把常用任务参数保存为可复用模板，
//    runAgentTemplate 一键按模板创建并立即执行任务。
import { request } from './request'
import type { AgentTaskResp, AgentTemplateItem } from '@/types'

export function createAgentTask(payload: {
  task_type: 'weekly_report' | 'doc_compare' | 'write_plan'
  doc_ids: number[]
  params?: Record<string, unknown>
  model_provider_id?: number | null
  template_id?: number | null
  canvas_json?: string | null
}) {
  return request<AgentTaskResp>({
    url: '/agent/tasks',
    method: 'post',
    data: {
      task_type: payload.task_type,
      doc_ids: payload.doc_ids,
      params: payload.params || {},
      model_provider_id: payload.model_provider_id ?? null,
      template_id: payload.template_id ?? null,
      canvas_json: payload.canvas_json ?? null,
    },
  })
}

export function confirmAgentTask(taskId: number, confirm: boolean) {
  return request<AgentTaskResp>({
    url: `/agent/tasks/${taskId}/confirm`,
    method: 'post',
    data: { confirm },
  })
}

export function listAgentTasks() {
  return request<AgentTaskResp[]>({
    url: '/agent/tasks',
    method: 'get',
  })
}

export function getAgentTask(taskId: number) {
  return request<AgentTaskResp>({
    url: `/agent/tasks/${taskId}`,
    method: 'get',
  })
}

/* ---------------- 工作流模板 ---------------- */

export function listAgentTemplates() {
  return request<AgentTemplateItem[]>({
    url: '/agent/templates',
    method: 'get',
  })
}

export function createAgentTemplate(payload: {
  template_name: string
  task_type: string
  doc_ids?: number[]
  params?: Record<string, unknown>
  canvas_json?: string | null
}) {
  return request<AgentTemplateItem>({
    url: '/agent/templates',
    method: 'post',
    data: {
      template_name: payload.template_name,
      task_type: payload.task_type,
      doc_ids: payload.doc_ids || [],
      params: payload.params || {},
      canvas_json: payload.canvas_json || null,
    },
  })
}

export function updateAgentTemplate(
  templateId: number,
  payload: {
    template_name: string
    task_type: string
    doc_ids?: number[]
    params?: Record<string, unknown>
    canvas_json?: string | null
  },
) {
  return request<AgentTemplateItem>({
    url: `/agent/templates/${templateId}`,
    method: 'put',
    data: {
      template_name: payload.template_name,
      task_type: payload.task_type,
      doc_ids: payload.doc_ids || [],
      params: payload.params || {},
      canvas_json: payload.canvas_json || null,
    },
  })
}

export function deleteAgentTemplate(templateId: number) {
  return request<{ message?: string }>({
    url: `/agent/templates/${templateId}`,
    method: 'delete',
  })
}

export function runAgentTemplate(templateId: number) {
  return request<AgentTaskResp>({
    url: `/agent/templates/${templateId}/run`,
    method: 'post',
  })
}

