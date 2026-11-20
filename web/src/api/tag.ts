/**
 * 标签辅助：后端未提供独立的 GET /tag 接口，
 * 前端从文档列表 items 中聚合全部标签作为筛选项/编辑候选。
 */
import type { DocListItem } from '@/types'

/** 从文档列表聚合去重标签 */
export function collectTags(items: DocListItem[]): string[] {
  const set = new Set<string>()
  items.forEach((item) => {
    ;(item.tags || []).forEach((t) => set.add(t))
  })
  return Array.from(set).sort((a, b) => a.localeCompare(b, 'zh'))
}

/** 为标签编辑弹窗提供候选：合并既有标签与用户输入 */
export function mergeTagCandidates(existing: string[], input: string[]): string[] {
  const set = new Set<string>([...existing, ...input.map((s) => s.trim()).filter(Boolean)])
  return Array.from(set)
}
