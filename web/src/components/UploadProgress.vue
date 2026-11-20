<script setup lang="ts">
/**
 * 上传解析进度弹窗：轮询文档详情获取 progress，按阶段切换文案
 * 阶段文案：解析(10) -> OCR(40) -> 切片(70) -> 向量化(90) -> 完成(100)/失败
 */
import { ref, computed, onBeforeUnmount } from 'vue'
import { getDocumentDetail } from '@/api/document'
import type { DocDetail } from '@/types'
import { ElMessage } from 'element-plus'

const props = defineProps<{
  modelValue: boolean
  docId: number
  docName: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'finished', doc: DocDetail): void
  (e: 'retry'): void
}>()

const detail = ref<DocDetail | null>(null)
const failed = ref(false)
const failMsg = ref('')
const timer = ref<number | null>(null)
const stuckWarned = ref(false)
let lastProgress = -1
let lastChangeTime = 0

const progress = computed(() => detail.value?.progress ?? 0)
const status = computed(() => detail.value?.status ?? 'processing')

const stageText = computed(() => {
  if (status.value === 'failed') return '解析失败'
  const p = progress.value
  if (p >= 100) return '解析完成'
  if (p >= 90) return '向量化中'
  if (p >= 70) return '切片中'
  if (p >= 40) return 'OCR 识别中'
  if (p >= 10) return '解析中'
  return '等待处理'
})

const stageIcon = computed(() => {
  if (status.value === 'failed') return '✕'
  if (progress.value >= 100) return '✓'
  return '…'
})

function stopPolling() {
  if (timer.value !== null) {
    window.clearInterval(timer.value)
    timer.value = null
  }
}

async function poll() {
  try {
    const d = await getDocumentDetail(props.docId)
    detail.value = d
    if (d.status === 'success') {
      stopPolling()
      ElMessage.success('文档解析完成')
      emit('finished', d)
    } else if (d.status === 'failed') {
      stopPolling()
      failed.value = true
      failMsg.value = d.fail_msg || '解析失败，请查看详情'
    } else if (!stuckWarned.value) {
      // 解析进度长时间未推进时提示，避免用户误以为页面卡死
      const now = Date.now()
      if (d.progress !== lastProgress) {
        lastProgress = d.progress
        lastChangeTime = now
      } else if (lastChangeTime > 0 && now - lastChangeTime > 90000) {
        stuckWarned.value = true
        ElMessage.warning('解析进度长时间未更新，可关闭弹窗稍后在文档列表查看状态')
      }
    }
  } catch {
    // 轮询请求失败不中断，等待下轮
  }
}

function open() {
  failed.value = false
  failMsg.value = ''
  detail.value = null
  stuckWarned.value = false
  lastProgress = -1
  lastChangeTime = 0
  poll()
  timer.value = window.setInterval(poll, 1000)
}

function handleClosed() {
  stopPolling()
}

const dialogVisible = computed({
  get: () => props.modelValue,
  set: (v: boolean) => {
    emit('update:modelValue', v)
  },
})
</script>

<template>
  <el-dialog
    :model-value="dialogVisible"
    append-to-body
    title="文档上传与解析"
    width="480px"
    :close-on-click-modal="false"
    @open="open"
    @closed="handleClosed"
    @update:model-value="dialogVisible = $event"
  >
    <div class="upload-progress">
      <div class="doc-name">{{ docName }}</div>
      <el-progress
        :percentage="progress"
        :status="status === 'failed' ? 'exception' : progress >= 100 ? 'success' : undefined"
        :stroke-width="10"
      />
      <div class="stage" :class="{ failed }">
        <span class="stage-icon">{{ stageIcon }}</span>
        <span>{{ stageText }}</span>
        <span v-if="progress < 100 && status !== 'failed'" class="percent">{{ progress }}%</span>
      </div>
      <div v-if="failed" class="fail-msg">{{ failMsg || '解析失败' }}</div>
      <div v-else class="hint">解析包含四阶段：解析 → OCR → 切片 → 向量化，请稍候…</div>
    </div>

    <template #footer>
      <el-button v-if="failed" type="primary" @click="emit('retry')">重新解析</el-button>
      <el-button @click="dialogVisible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.upload-progress {
  padding: 8px 4px;
}

.doc-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--ks-text-title);
  margin-bottom: 18px;
  word-break: break-all;
}

.stage {
  margin-top: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: var(--ks-text-body);
}

.stage.failed {
  color: var(--ks-danger);
}

.stage-icon {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--ks-primary-light);
  color: var(--ks-primary);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
}

.stage.failed .stage-icon {
  background: #fee2e2;
  color: var(--ks-danger);
}

.percent {
  color: var(--ks-primary);
  font-weight: 600;
}

.hint {
  margin-top: 12px;
  font-size: 12px;
  color: var(--ks-text-secondary);
}

.fail-msg {
  margin-top: 12px;
  font-size: 13px;
  color: var(--ks-danger);
  background: #fef2f2;
  border-radius: 6px;
  padding: 10px 12px;
  word-break: break-all;
}
</style>
