<script setup lang="ts">
/**
 * 溯源引用弹窗：展示引用切片原文 + 页码/工作表，本地分页浏览
 */
import { ref, computed, watch } from 'vue'
import type { Citation, KgEntity } from '@/types'

const props = defineProps<{
  modelValue: boolean
  citations: Citation[]
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
}>()

const PAGE_SIZE = 5
const current = ref(1)

watch(
  () => props.modelValue,
  (v) => {
    if (v) current.value = 1
  },
)

const total = computed(() => props.citations.length)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))
const pageItems = computed(() => {
  const start = (current.value - 1) * PAGE_SIZE
  return props.citations.slice(start, start + PAGE_SIZE)
})

function formatLocation(c: Citation): string {
  const parts: string[] = []
  if (c.page_no) parts.push(`第 ${c.page_no} 页`)
  if (c.sheet_name) parts.push(`工作表：${c.sheet_name}`)
  return parts.join(' · ') || '片段'
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    append-to-body
    title="溯源引用"
    width="640px"
    :close-on-click-modal="false"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <template v-if="citations.length">
      <div class="cite-list">
        <div v-for="(c, i) in pageItems" :key="c.chunk_id" class="cite-item">
          <div class="cite-head">
            <span class="cite-no">{{ (current - 1) * PAGE_SIZE + i + 1 }}</span>
            <span class="cite-doc">{{ c.doc_name }}</span>
            <span class="cite-loc">{{ formatLocation(c) }}</span>
          </div>
          <div class="cite-content">{{ c.content }}</div>
          <div v-if="c.related_entities?.length" class="cite-entities">
            <span class="cite-entities-label"><el-icon :size="13"><Connection /></el-icon> 关联知识图谱</span>
            <div class="cite-entities-list">
              <span
                v-for="(e, ei) in (c.related_entities as KgEntity[])"
                :key="`${e.id}-${ei}`"
                class="cite-entity-chip"
                :title="e.description || e.name"
              >
                {{ e.name }}
                <em>{{ e.type }}</em>
              </span>
            </div>
          </div>
        </div>
      </div>

      <div class="cite-footer">
        <el-pagination
          layout="prev, pager, next"
          :total="total"
          :page-size="PAGE_SIZE"
          :current-page="current"
          @current-change="(p: number) => (current = p)"
        />
        <span class="ks-muted">共 {{ total }} 条引用</span>
      </div>
    </template>

    <el-empty v-else description="暂无引用片段" />
  </el-dialog>
</template>

<style scoped>
.cite-list {
  max-height: 420px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.cite-item {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px 14px;
  background: #f8fafc;
}

.cite-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.cite-no {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--ks-primary);
  color: #fff;
  font-size: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  flex-shrink: 0;
}

.cite-doc {
  font-size: 13px;
  font-weight: 600;
  color: var(--ks-text-title);
}

.cite-loc {
  font-size: 12px;
  color: var(--ks-text-secondary);
}

.cite-content {
  font-size: 13px;
  line-height: 1.6;
  color: var(--ks-text-body);
  max-height: 96px;
  overflow-y: auto;
  white-space: pre-wrap;
}

/* GraphRAG 关联实体 */
.cite-entities {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed #dbe3ee;
}

.cite-entities-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 700;
  color: var(--ks-primary-active);
  margin-bottom: 8px;
}

.cite-entities-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.cite-entity-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  font-weight: 600;
  color: var(--ks-text-body);
  background: var(--ks-primary-soft);
  border: 1px solid rgba(37, 99, 235, 0.16);
  border-radius: 999px;
  padding: 3px 9px;
  cursor: default;
  transition: all 0.2s ease;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cite-entity-chip em {
  font-style: normal;
  font-size: 11px;
  color: var(--ks-text-secondary);
  background: rgba(255, 255, 255, 0.7);
  border-radius: 999px;
  padding: 1px 7px;
}

.cite-entity-chip:hover {
  border-color: var(--ks-primary);
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.18);
}

.cite-footer {
  margin-top: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
</style>
