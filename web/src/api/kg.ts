/**
 * 知识图谱（GraphRAG）接口
 */
// ===== 逐行注释：图谱接口封装 =====
// 1. extractDocumentKg：手动触发单文档实体+关系抽取（POST /kg/extract/{docId}），
//    返回抽取结果（实体/关系数量），图谱页"重新抽取"按钮调用。
// 2. getKgGraph：拉取图谱节点/边数据，支持 doc_id（按文档过滤）与 keyword（关键词过滤）
//    limit（节点数量上限），供 ECharts 力导向图渲染。
// 3. searchKgEntities：实体名模糊搜索（供图谱搜索框联想/定位节点）。
// 4. getKgStats：图谱统计（实体总数/关系总数/已抽取文档数），供图谱页统计卡片展示。
import { request } from './request'
import type { KgExtractResult, KgGraphData, KgStats, KgEntity } from '@/types'

/** 手动触发文档实体抽取 */
export function extractDocumentKg(docId: number) {
  return request<KgExtractResult>({
    url: `/kg/extract/${docId}`,
    method: 'post',
  })
}

/** 图谱数据（支持按文档 / 关键词过滤） */
export function getKgGraph(params?: { doc_id?: number; keyword?: string; limit?: number }) {
  return request<KgGraphData>({
    url: '/kg/graph',
    method: 'get',
    params: params || {},
  })
}

/** 实体搜索 */
export function searchKgEntities(keyword: string, limit = 20) {
  return request<KgEntity[]>({
    url: '/kg/search',
    method: 'get',
    params: { keyword, limit },
  })
}

/** 图谱统计 */
export function getKgStats() {
  return request<KgStats>({
    url: '/kg/stats',
    method: 'get',
  })
}
