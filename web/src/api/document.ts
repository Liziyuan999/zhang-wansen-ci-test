/**
 * 文档接口：上传 / 列表 / 详情 / 版本 / 标签 / 删除 / 下载 / 导出
 */
// ===== 逐行注释：文档接口封装 =====
// 1. 上传类（uploadDocument / uploadVersion）：构造 FormData（multipart），
//    注意 axios 实例 request 在 request.ts 中会统一注入 Authorization 头。
// 2. 查询类（listDocuments / getDocumentDetail）：分页参数 keyword/file_type/status/tag
//    与后端 SQL 筛选一一对应，返回 PageResult<DocListItem> 分页结构。
// 3. 下载类（downloadDocument）：走 instance 原始实例 + responseType:'blob'，
//    避免 request 包装层对二进制响应的 JSON 解析；返回 Blob 供前端触发浏览器下载。
// 4. 变更类（assignTags / updateDocMeta / deleteDocument / reprocessDocument）：
//    分别对应标签覆盖、元信息 patch、软删除（后端置 is_deleted）、重新解析（清空切片重跑）。
// 5. exportDocuments：导出清单 xlsx。后端 download=true 直接回传二进制流，
//    前端与 downloadDocument 一致走 blob 落地，避免只拿到服务器路径而无法真正下载。
import { request, instance } from './request'
import type { DocDetail, DocListItem, PageResult } from '@/types'

/** 上传新文档（multipart） */
export function uploadDocument(file: File, doc_name = '', tag_names: string[] = []) {
  const form = new FormData()
  form.append('file', file)
  if (doc_name) form.append('doc_name', doc_name)
  if (tag_names.length) form.append('tag_names', tag_names.join(','))
  return request<DocDetail>({
    url: '/documents/upload',
    method: 'post',
    data: form,
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

/** 上传新版本（multipart） */
export function uploadVersion(docId: number, file: File) {
  const form = new FormData()
  form.append('file', file)
  return request<{ doc_id: number; version_no: number }>({
    url: `/documents/${docId}/versions`,
    method: 'post',
    data: form,
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

/** 文档列表（分页 + 筛选） */
export function listDocuments(params: {
  keyword?: string
  file_type?: string
  status?: string
  tag?: string
  page?: number
  page_size?: number
}) {
  return request<PageResult<DocListItem>>({
    url: '/documents',
    method: 'get',
    params,
  })
}

/** 文档详情（含解析进度 progress / 失败原因 fail_msg / 抽取结果） */
export function getDocumentDetail(docId: number) {
  return request<DocDetail>({
    url: `/documents/${docId}`,
    method: 'get',
  })
}

/** 下载原始文件（blob） */
export async function downloadDocument(docId: number): Promise<Blob> {
  const resp = await instance.get(`/documents/${docId}/download`, {
    responseType: 'blob',
  })
  return resp.data as Blob
}

/** 更新标签 */
export function assignTags(docId: number, tag_names: string[]) {
  return request<{ tags: string[] }>({
    url: `/documents/${docId}/tags`,
    method: 'post',
    data: { tag_names },
  })
}

/** 更新文档元信息（名称/标签） */
export function updateDocMeta(docId: number, payload: { doc_name?: string; tag_names?: string[] }) {
  return request<DocListItem>({
    url: `/documents/${docId}`,
    method: 'patch',
    data: payload,
  })
}

/** 删除文档 */
export function deleteDocument(docId: number) {
  return request<void>({
    url: `/documents/${docId}`,
    method: 'delete',
  })
}

/** 重新解析文档（失败/已完成状态可重试，清空旧切片后后台重新解析） */
export function reprocessDocument(docId: number) {
  return request<{ doc_id: number; status: string }>({
    url: `/documents/${docId}/reprocess`,
    method: 'post',
  })
}

/** 导出文档清单 xlsx（后端直接回传二进制流，前端按 Blob 落地保存） */
export async function exportDocuments(params: { keyword?: string; file_type?: string }): Promise<Blob> {
  const resp = await instance.get('/documents/export', {
    params: { ...params, download: true },
    responseType: 'blob',
  })
  return resp.data as Blob
}
